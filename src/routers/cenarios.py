"""
cenarios.py — Router dos cenários de alocação.

Um cenário é uma alocação completa e autocontida. Importar ou reexecutar não
apaga o que já existe: cria um novo cenário. É o que sustenta o histórico de
versões.

Referência: SAA_Arquitetura.pdf, seções 5 e 10.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import TURNOS, Pavimento as PavimentoDominio
from src.domain.importacao import Catalogo, importar, normalizar, para_clinicas
from src.domain.importacao.leitor import ErroDeLeitura
from src.models.saa import Alocacao
from src.repositories import (
    AlocacaoRepository,
    CatalogoRepository,
    PavimentoEntrada,
    RestricaoPadraoEntrada,
)
from src.resources.database import get_app_db_session
from src.services import (
    AlocacaoService,
    GradesService,
    PanoramaService,
    ProcessoService,
    RestricoesService,
    VisualizacaoService,
    pesos_do_motor,
    resolver_regras_padrao,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cenarios", tags=["Cenários"])

EXTENSOES_ACEITAS = {".csv", ".xlsx", ".xls"}


# ---------------------------------------------------------------------------
# Panorama padrão — vem do catálogo, não de constantes no código
# ---------------------------------------------------------------------------


def _pavimento_catalogo_dict(p) -> dict:
    return {
        "id": p.id,
        "bloco": p.bloco,
        "nome": p.nome,
        "andar": p.andar,
        "nome_completo": f"{p.bloco} — {p.nome}",
        "padrao_1est": p.padrao_1est,
        "padrao_2est": p.padrao_2est,
        "esp_1est": p.esp_1est,
        "esp_2est": p.esp_2est,
        "fechada": p.fechada,
        "capacidade": p.capacidade,
    }


@router.get(
    "/padroes",
    summary="Estrutura do prédio e malha de turnos",
    description=(
        "Pavimentos do catálogo global, com as contagens de salas por tipo e a "
        "capacidade derivada. Na primeira chamada o catálogo é semeado."
    ),
)
async def obter_padroes(sessao: AsyncSession = Depends(get_app_db_session)):
    catalogo = CatalogoRepository(sessao)
    if any((await catalogo.semear_referencia()).values()):
        await sessao.commit()

    pavimentos = await catalogo.listar_pavimentos()
    return {
        "pavimentos": [_pavimento_catalogo_dict(p) for p in pavimentos],
        "capacidade_total": sum(p.capacidade for p in pavimentos),
        "turnos": [{"dia": d, "periodo": t} for d, t in TURNOS],
        "unidades_excluidas": sorted(await catalogo.unidades_excluidas()),
    }


class EdicaoPavimentoPadrao(BaseModel):
    pavimento_id: int
    contagens: dict[str, int]


@router.put(
    "/padroes",
    summary="Editar o panorama de salas padrão (catálogo) em lote",
    description=(
        "Ajusta as contagens de salas dos pavimentos do catálogo. Vale só para "
        "cenários futuros; os já criados guardam a própria cópia."
    ),
)
async def editar_padroes(
    edicoes: list[EdicaoPavimentoPadrao],
    sessao: AsyncSession = Depends(get_app_db_session),
):
    catalogo = CatalogoRepository(sessao)
    await catalogo.semear_referencia()
    try:
        for edicao in edicoes:
            alterado = await catalogo.editar_pavimento_padrao(
                edicao.pavimento_id, edicao.contagens
            )
            if alterado is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f"pavimento {edicao.pavimento_id} não existe no catálogo",
                )
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    pavimentos = await catalogo.listar_pavimentos()
    return {
        "pavimentos": [_pavimento_catalogo_dict(p) for p in pavimentos],
        "capacidade_total": sum(p.capacidade for p in pavimentos),
    }


# ---------------------------------------------------------------------------
# Regras padrão — catálogo global de obrigatoriedade/preferência
#
# Por Unidade_Funcional + pavimento. Aplicadas como pré-configuração a cada
# NOVO cenário (ver `_resolver_restricoes_padrao`, mais abaixo). Editar ou
# remover uma regra aqui não altera cenários já criados — cada um guarda sua
# própria cópia das restrições desde a criação.
#
# Registradas antes de `/{cenario_id}` de propósito: rotas estáticas precisam
# vir antes das dinâmicas, senão "/regras-padrao" seria interpretado como um
# `cenario_id` inválido.
# ---------------------------------------------------------------------------


class NovaRegraPadrao(BaseModel):
    unidade: str
    pavimento_catalogo_id: int
    tipo: str


def _serializar_regra_padrao(r) -> dict:
    return {
        "id": r.id,
        "unidade": r.nome_unidade,
        "pavimento_catalogo_id": r.pavimento_catalogo_id,
        "pavimento": f"{r.pavimento.bloco} — {r.pavimento.nome}",
        "tipo": r.tipo,
    }


@router.get(
    "/regras-padrao",
    summary="Listar as regras padrão (obrigatoriedade/preferência) do catálogo",
    description=(
        "Regras por Unidade_Funcional + pavimento aplicadas como pré-"
        "configuração a cada NOVO cenário. Editar aqui não altera cenários já "
        "criados."
    ),
)
async def listar_regras_padrao(sessao: AsyncSession = Depends(get_app_db_session)):
    catalogo = CatalogoRepository(sessao)
    if any((await catalogo.semear_referencia()).values()):
        await sessao.commit()

    regras = await catalogo.listar_restricoes_padrao()
    unidades = await catalogo.listar_unidades()
    # Só pavimentos com capacidade servem de destino de uma regra.
    pavimentos = [p for p in await catalogo.listar_pavimentos() if p.capacidade > 0]

    return {
        "regras": [_serializar_regra_padrao(r) for r in regras],
        # As 62 unidades do catálogo — o gestor pode restringir qualquer uma; só
        # as participantes de um cenário herdam a regra na prática.
        "unidades": [
            {"nome": u.nome, "participa_default": u.participa_default} for u in unidades
        ],
        "pavimentos": [
            {"id": p.id, "nome_completo": f"{p.bloco} — {p.nome}"} for p in pavimentos
        ],
    }


@router.post(
    "/regras-padrao",
    status_code=status.HTTP_201_CREATED,
    summary="Definir uma regra padrão",
)
async def definir_regra_padrao(
    nova: NovaRegraPadrao, sessao: AsyncSession = Depends(get_app_db_session)
):
    catalogo = CatalogoRepository(sessao)
    try:
        await catalogo.definir_restricao_padrao(
            nova.unidade, nova.pavimento_catalogo_id, nova.tipo
        )
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))
    await sessao.commit()
    regras = await catalogo.listar_restricoes_padrao()
    return {"regras": [_serializar_regra_padrao(r) for r in regras]}


@router.delete("/regras-padrao/{regra_id}", summary="Remover uma regra padrão")
async def remover_regra_padrao(
    regra_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    catalogo = CatalogoRepository(sessao)
    if not await catalogo.remover_restricao_padrao(regra_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"regra padrão {regra_id} não encontrada"
        )
    await sessao.commit()
    return {"removida": True}


# ---------------------------------------------------------------------------
# Criar um cenário a partir de uma planilha
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Criar um cenário a partir da exportação do AGHU",
    description=(
        "Roda o pipeline de tratamento, executa o motor de alocação e grava "
        "tudo como um cenário autocontido."
    ),
)
async def criar_cenario(
    arquivo: UploadFile = File(..., description="Exportação do AGHU (.csv ou .xlsx)"),
    nome: str = Form(..., description="Nome do cenário"),
    pavimentos: str | None = Form(
        None, description='JSON com as contagens de salas por pavimento'
    ),
    unidades_excluidas: str | None = Form(
        None, description='JSON: ["ALMOXARIFADO", ...]'
    ),
    sessao: AsyncSession = Depends(get_app_db_session),
):
    nome_cenario = nome.strip()
    if not nome_cenario:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="o cenário precisa de um nome",
        )

    nome_arquivo = arquivo.filename or "grades.csv"
    sufixo = Path(nome_arquivo).suffix.lower()
    if sufixo not in EXTENSOES_ACEITAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"extensão não suportada: {sufixo or '(nenhuma)'}",
        )

    catalogo = CatalogoRepository(sessao)
    await catalogo.semear_referencia()
    entradas = await _pavimentos(pavimentos, sessao)

    # Exclusões: escolha explícita do gestor, ou o padrão do catálogo.
    if unidades_excluidas is None:
        excluidas_norm = await catalogo.unidades_excluidas()
    else:
        excluidas_norm = frozenset(
            normalizar(n) for n in _lista(unidades_excluidas, "unidades_excluidas")
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="o arquivo enviado está vazio",
        )

    temporario = Path(tempfile.gettempdir()) / f"saa_cenario_{id(conteudo)}{sufixo}"
    try:
        temporario.write_bytes(conteudo)
        try:
            importacao = importar(
                temporario, Catalogo(unidades_excluidas=excluidas_norm)
            )
        except ErroDeLeitura as erro:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)
            )
    finally:
        temporario.unlink(missing_ok=True)

    clinicas = para_clinicas(importacao.demandas)

    # As unidades que apareceram no arquivo mas foram excluídas ficam
    # registradas no cenário com o nome original, participa=False.
    excluidas_vistas = tuple(
        nome
        for nome in importacao.unidades_vistas
        if normalizar(nome) in excluidas_norm
    )

    # Pré-configuração: as regras padrão do catálogo (obrigatoriedade/preferência
    # por Unidade_Funcional + pavimento) viram restrições deste cenário novo. É
    # só o ponto de partida — o gestor edita/remove na etapa 4 sem alterar o
    # padrão global, e o padrão global só afeta cenários criados depois dele.
    #
    # Resolvidas ANTES do motor rodar de propósito: a pré-alocação (a execução
    # inicial, aqui) já precisa sair ponderada por elas — não só depois que o
    # gestor reexecutar a etapa 5 manualmente.
    restricoes_padrao = await _resolver_restricoes_padrao(catalogo, entradas)

    resultado = None
    if clinicas and entradas:
        dominio = tuple(
            PavimentoDominio(id=i, nome=e.nome_completo, capacidade=e.capacidade)
            for i, e in enumerate(entradas, start=1)
        )
        obrigatorias, afinidade = pesos_do_motor(
            (
                (r.unidade_normalizada, r.pavimento_indice, r.tipo)
                for r in restricoes_padrao
            ),
            clinicas,
        )
        resultado = SolverHeuristico().resolver(
            EntradaAlocacao(
                clinicas=clinicas,
                pavimentos=dominio,
                obrigatorias=obrigatorias,
                afinidade=afinidade,
            )
        )

    # O catálogo aprende as unidades novas que o arquivo trouxe.
    await catalogo.aprender_unidades(list(importacao.unidades_vistas))

    repo = AlocacaoRepository(sessao)
    cenario = await repo.criar(
        nome=nome_cenario,
        clinicas=clinicas,
        slots=importacao.slots,
        demandas=importacao.demandas,
        pavimentos=entradas,
        resultado=resultado,
        unidades_excluidas=excluidas_vistas,
        restricoes_padrao=restricoes_padrao,
    )
    cenario_id = cenario.id
    await sessao.commit()
    sessao.expunge_all()

    logger.info("cenário %d criado a partir de %s", cenario_id, nome_arquivo)
    return await _detalhar(repo, cenario_id)


# ---------------------------------------------------------------------------
# Histórico
# ---------------------------------------------------------------------------


@router.get("", summary="Listar cenários", description="Do mais recente ao mais antigo.")
async def listar_cenarios(sessao: AsyncSession = Depends(get_app_db_session)):
    repo = AlocacaoRepository(sessao)
    cenarios = await repo.listar()
    return [
        {
            "id": c.id,
            "nome": c.nome,
            "status": c.status,
            "etapa_atual": c.etapa_atual,
            "criado_em": c.criado_em.isoformat() if c.criado_em else None,
            "origem_id": c.origem_id,
            "unidades": sum(1 for u in c.unidades if u.participa),
            "pavimentos": len(c.pavimentos),
        }
        for c in cenarios
    ]


@router.get("/{cenario_id}", summary="Abrir um cenário")
async def obter_cenario(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    return await _detalhar(AlocacaoRepository(sessao), cenario_id)


@router.post(
    "/{cenario_id}/clonar",
    status_code=status.HTTP_201_CREATED,
    summary="Duplicar um cenário para criar uma variação",
)
async def clonar_cenario(
    cenario_id: int,
    nome: str = Form(...),
    sessao: AsyncSession = Depends(get_app_db_session),
):
    repo = AlocacaoRepository(sessao)
    clone = await repo.clonar(cenario_id, nome.strip() or "Cópia")
    if clone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cenário {cenario_id} não encontrado",
        )
    novo_id = clone.id
    await sessao.commit()
    sessao.expunge_all()
    return await _detalhar(repo, novo_id)


@router.delete(
    "/{cenario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Excluir um cenário",
)
async def excluir_cenario(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    repo = AlocacaoRepository(sessao)
    if not await repo.excluir(cenario_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cenário {cenario_id} não encontrado",
        )
    await sessao.commit()


# ---------------------------------------------------------------------------
# Etapas — a máquina de estados (seção 7)
# ---------------------------------------------------------------------------


@router.get("/{cenario_id}/etapas", summary="Status das 6 etapas")
async def listar_etapas(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    return {
        "etapa_atual": cenario.etapa_atual,
        "status": cenario.status,
        "etapas": ProcessoService(sessao).resumo(cenario),
    }


@router.post("/{cenario_id}/etapas/{numero}", summary="Ir para uma etapa")
async def ir_para_etapa(
    cenario_id: int, numero: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    processo = ProcessoService(sessao)
    try:
        await processo.ir_para(cenario, numero)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))
    await sessao.commit()
    return {"etapa_atual": cenario.etapa_atual, "etapas": processo.resumo(cenario)}


@router.post("/{cenario_id}/concluir", summary="Concluir o cenário")
async def concluir_cenario(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    try:
        await ProcessoService(sessao).concluir(cenario)
    except ValueError as erro:
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))
    await sessao.commit()
    return {"status": cenario.status}


# ---------------------------------------------------------------------------
# Etapa 2 — grades
# ---------------------------------------------------------------------------


class CelulaGrade(BaseModel):
    unidade_id: int
    dia: str
    turno: str
    quantidade: int


class EdicaoGrades(BaseModel):
    """Edição em lote: só as células alteradas."""

    celulas: list[CelulaGrade] = Field(default_factory=list)
    participacao: dict[int, bool] = Field(default_factory=dict)


@router.get("/{cenario_id}/grades", summary="Ler a planilha de grades")
async def ler_grades(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    servico = GradesService(sessao)
    return {
        "turnos": [{"dia": d, "periodo": t} for d, t in TURNOS],
        "unidades": servico.ler(cenario),
        "totais_por_turno": servico.totais_por_turno(cenario),
    }


@router.put("/{cenario_id}/grades", summary="Editar grades em lote")
async def editar_grades(
    cenario_id: int,
    edicao: EdicaoGrades,
    sessao: AsyncSession = Depends(get_app_db_session),
):
    cenario = await _carregar(sessao, cenario_id)
    servico = GradesService(sessao)
    try:
        for celula in edicao.celulas:
            await servico.editar_demanda(
                cenario, celula.unidade_id, celula.dia, celula.turno, celula.quantidade
            )
        for unidade_id, participa in edicao.participacao.items():
            await servico.definir_participacao(cenario, unidade_id, participa)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    return {
        "unidades": servico.ler(cenario),
        "totais_por_turno": servico.totais_por_turno(cenario),
        "etapas": ProcessoService(sessao).resumo(cenario),
    }


# ---------------------------------------------------------------------------
# Etapa 3 — panorama de salas
# ---------------------------------------------------------------------------


class EdicaoPavimento(BaseModel):
    pavimento_id: int
    contagens: dict[str, int]


@router.get("/{cenario_id}/panorama", summary="Ler o panorama de salas")
async def ler_panorama(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    servico = PanoramaService(sessao)
    return {
        "pavimentos": servico.ler(cenario),
        "capacidade_total": servico.capacidade_total(cenario),
    }


@router.put("/{cenario_id}/panorama", summary="Editar o panorama em lote")
async def editar_panorama(
    cenario_id: int,
    edicoes: list[EdicaoPavimento],
    sessao: AsyncSession = Depends(get_app_db_session),
):
    cenario = await _carregar(sessao, cenario_id)
    servico = PanoramaService(sessao)
    try:
        for edicao in edicoes:
            await servico.editar(cenario, edicao.pavimento_id, edicao.contagens)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    return {
        "pavimentos": servico.ler(cenario),
        "capacidade_total": servico.capacidade_total(cenario),
        "etapas": ProcessoService(sessao).resumo(cenario),
    }


# ---------------------------------------------------------------------------
# Etapa 4 — obrigatoriedades e preferências
# ---------------------------------------------------------------------------


class NovaRestricao(BaseModel):
    unidade_id: int
    pavimento_id: int
    tipo: str


@router.get("/{cenario_id}/restricoes", summary="Listar restrições")
async def ler_restricoes(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    return {"restricoes": RestricoesService(sessao).listar(cenario)}


@router.post(
    "/{cenario_id}/restricoes",
    status_code=status.HTTP_201_CREATED,
    summary="Definir obrigatoriedade ou preferência",
)
async def definir_restricao(
    cenario_id: int,
    nova: NovaRestricao,
    sessao: AsyncSession = Depends(get_app_db_session),
):
    cenario = await _carregar(sessao, cenario_id)
    servico = RestricoesService(sessao)
    try:
        await servico.definir(cenario, nova.unidade_id, nova.pavimento_id, nova.tipo)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    return {"restricoes": servico.listar(cenario)}


@router.delete(
    "/{cenario_id}/restricoes/{restricao_id}", summary="Remover uma restrição"
)
async def remover_restricao(
    cenario_id: int,
    restricao_id: int,
    sessao: AsyncSession = Depends(get_app_db_session),
):
    cenario = await _carregar(sessao, cenario_id)
    servico = RestricoesService(sessao)
    if not await servico.remover(cenario, restricao_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"restrição {restricao_id} não encontrada"
        )
    await sessao.commit()
    return {"restricoes": servico.listar(cenario)}


# ---------------------------------------------------------------------------
# Etapas 5 e 6 — executar e ajustar
# ---------------------------------------------------------------------------


class MoverClinica(BaseModel):
    unidade_id: int
    pavimento_id: int


@router.post("/{cenario_id}/alocar", summary="Executar o motor de alocação")
async def alocar(cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)):
    cenario = await _carregar(sessao, cenario_id)
    try:
        await AlocacaoService(sessao).executar(cenario)
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    sessao.expunge_all()
    return await _detalhar(AlocacaoRepository(sessao), cenario_id)


@router.put("/{cenario_id}/alocacao", summary="Ajuste manual: mover clínica de pavimento")
async def mover_clinica(
    cenario_id: int,
    movimento: MoverClinica,
    sessao: AsyncSession = Depends(get_app_db_session),
):
    cenario = await _carregar(sessao, cenario_id)
    try:
        await AlocacaoService(sessao).mover(
            cenario, movimento.unidade_id, movimento.pavimento_id
        )
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    sessao.expunge_all()
    return await _detalhar(AlocacaoRepository(sessao), cenario_id)


# ---------------------------------------------------------------------------
# Visualização — painel consolidado, somente leitura
# ---------------------------------------------------------------------------


@router.get(
    "/{cenario_id}/visualizacao",
    summary="Painel consolidado da alocação (somente leitura)",
)
async def visualizar(
    cenario_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    cenario = await _carregar(sessao, cenario_id)
    try:
        return VisualizacaoService(sessao).montar(cenario)
    except ValueError as erro:
        # 409: o cenário existe, mas ainda não está num estado visualizável.
        raise HTTPException(status.HTTP_409_CONFLICT, str(erro))


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


async def _carregar(sessao: AsyncSession, cenario_id: int) -> Alocacao:
    cenario = await AlocacaoRepository(sessao).obter(cenario_id)
    if cenario is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"cenário {cenario_id} não encontrado"
        )
    return cenario


async def _detalhar(repo: AlocacaoRepository, cenario_id: int) -> dict:
    cenario = await repo.obter(cenario_id)
    if cenario is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"cenário {cenario_id} não encontrado",
        )

    pavimentos = {p.id: p for p in cenario.pavimentos}
    indices = {(dia, periodo): i for i, (dia, periodo) in enumerate(TURNOS)}

    unidades = []
    for unidade in cenario.unidades:
        alocado = [0] * len(TURNOS)
        nao_alocado = [0] * len(TURNOS)
        for item in unidade.resultados:
            i = indices.get((item.dia_semana, item.turno))
            if i is None:
                continue
            alocado[i] = item.qtd_alocada
            nao_alocado[i] = item.qtd_nao_alocada

        demanda = [0] * len(TURNOS)
        for item in unidade.demandas:
            i = indices.get((item.dia_semana, item.turno))
            if i is not None:
                demanda[i] = item.quantidade

        destino = pavimentos.get(unidade.pavimento_alocado_id or -1)
        unidades.append(
            {
                "id": unidade.id,
                "nome": unidade.unidade_nome,
                "participa": unidade.participa,
                # Bloco e pavimento (nome curto) separados — permite filtrar por
                # cada um independentemente na tela; o completo fica para
                # tooltip e para quem só quer o texto pronto.
                "pavimento_id": destino.id if destino else None,
                "bloco": destino.bloco if destino else None,
                "pavimento": destino.nome if destino else None,
                "pavimento_completo": destino.nome_completo if destino else None,
                "demanda": demanda,
                "alocado": alocado,
                "nao_alocado": nao_alocado,
                "total_alocado": sum(alocado),
                "total_nao_alocado": sum(nao_alocado),
                "slots_em_revisao": sum(1 for s in unidade.slots if s.revisar),
            }
        )

    return {
        "id": cenario.id,
        "nome": cenario.nome,
        "status": cenario.status,
        "etapa_atual": cenario.etapa_atual,
        "criado_em": cenario.criado_em.isoformat() if cenario.criado_em else None,
        "origem_id": cenario.origem_id,
        "turnos": [{"dia": d, "periodo": t} for d, t in TURNOS],
        "etapas": [{"numero": e.numero, "status": e.status} for e in cenario.etapas],
        "pavimentos": [
            {
                "id": p.id,
                "bloco": p.bloco,
                "nome": p.nome,
                "andar": p.andar,
                "nome_completo": p.nome_completo,
                "padrao_1est": p.padrao_1est,
                "padrao_2est": p.padrao_2est,
                "esp_1est": p.esp_1est,
                "esp_2est": p.esp_2est,
                "fechada": p.fechada,
                "capacidade": p.capacidade,
                "salas_abertas": p.salas_abertas,
            }
            for p in cenario.pavimentos
        ],
        "unidades": unidades,
        "total_alocado": sum(u["total_alocado"] for u in unidades),
        "total_nao_alocado": sum(u["total_nao_alocado"] for u in unidades),
    }


def _lista(bruto: str | None, campo: str) -> frozenset[str]:
    if not bruto:
        return frozenset()
    try:
        valores = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{campo} não é JSON válido: {erro}",
        )
    if not isinstance(valores, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{campo} deve ser uma lista de nomes",
        )
    return frozenset(str(v) for v in valores)


async def _resolver_restricoes_padrao(
    catalogo: CatalogoRepository, entradas: tuple[PavimentoEntrada, ...]
) -> tuple[RestricaoPadraoEntrada, ...]:
    """
    Resolve as regras padrão do catálogo contra os pavimentos deste cenário.

    Casa cada regra pelo (bloco, nome) do pavimento do catálogo com o índice
    1..N que `entradas` recebeu — o mesmo esquema usado pelo restante de
    `criar()`. Uma regra cujo pavimento não está entre os `entradas` deste
    cenário (ex.: painel de salas customizado sem aquele pavimento) é ignorada.
    """
    regras = await catalogo.listar_restricoes_padrao()
    if not regras:
        return ()

    resolvidas = resolver_regras_padrao(regras, [(e.bloco, e.nome) for e in entradas])
    return tuple(
        RestricaoPadraoEntrada(
            unidade_normalizada=unidade_normalizada,
            pavimento_indice=indice,
            tipo=tipo,
        )
        for unidade_normalizada, indice, tipo in resolvidas
    )


async def _pavimentos(
    bruto: str | None, sessao: AsyncSession
) -> tuple[PavimentoEntrada, ...]:
    """
    Lê as contagens enviadas pelo gestor ou cai no catálogo.

    A capacidade nunca vem do cliente — é sempre derivada das contagens, para
    não divergir do que a etapa 3 edita.
    """
    if not bruto:
        catalogo = CatalogoRepository(sessao)
        if any((await catalogo.semear_referencia()).values()):
            await sessao.commit()
        return tuple(
            PavimentoEntrada(
                bloco=p.bloco,
                nome=p.nome,
                andar=p.andar,
                padrao_1est=p.padrao_1est,
                padrao_2est=p.padrao_2est,
                esp_1est=p.esp_1est,
                esp_2est=p.esp_2est,
                fechada=p.fechada,
            )
            # Já vem ordenado por andar (catalogo.listar_pavimentos) — a
            # ordem aqui é a mesma que os índices 1..N atribuídos abaixo.
            for p in await catalogo.listar_pavimentos()
        )

    try:
        entradas = json.loads(bruto)
    except json.JSONDecodeError as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pavimentos não é JSON válido: {erro}",
        )
    if not isinstance(entradas, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="pavimentos deve ser uma lista",
        )

    try:
        return tuple(
            PavimentoEntrada(
                bloco=str(e.get("bloco") or ""),
                nome=str(e.get("nome") or f"Pavimento {i}"),
                andar=int(e.get("andar", 0)),
                padrao_1est=int(e.get("padrao_1est", 0)),
                padrao_2est=int(e.get("padrao_2est", 0)),
                esp_1est=int(e.get("esp_1est", 0)),
                esp_2est=int(e.get("esp_2est", 0)),
                fechada=int(e.get("fechada", 0)),
            )
            for i, e in enumerate(entradas, start=1)
        )
    except (AttributeError, TypeError, ValueError) as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pavimento inválido: {erro}",
        )
