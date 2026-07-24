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
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import TURNOS, Pavimento as PavimentoDominio
from src.domain.importacao import Catalogo, importar, para_clinicas
from src.domain.importacao.leitor import ErroDeLeitura
from src.repositories import AlocacaoRepository, CatalogoRepository, PavimentoEntrada
from src.resources.database import get_app_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/cenarios", tags=["Cenários"])

EXTENSOES_ACEITAS = {".csv", ".xlsx", ".xls"}


# ---------------------------------------------------------------------------
# Panorama padrão — vem do catálogo, não de constantes no código
# ---------------------------------------------------------------------------


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
    if await catalogo.semear_pavimentos():
        await sessao.commit()

    pavimentos = await catalogo.listar_pavimentos()
    return {
        "pavimentos": [
            {
                "bloco": p.bloco,
                "nome": p.nome,
                "nome_completo": f"{p.bloco} — {p.nome}",
                "padrao_1est": p.padrao_1est,
                "padrao_2est": p.padrao_2est,
                "esp_1est": p.esp_1est,
                "esp_2est": p.esp_2est,
                "fechada": p.fechada,
                "capacidade": p.capacidade,
            }
            for p in pavimentos
        ],
        "turnos": [{"dia": d, "periodo": t} for d, t in TURNOS],
        "unidades_excluidas": sorted(await catalogo.unidades_excluidas()),
    }


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

    excluidas = _lista(unidades_excluidas, "unidades_excluidas")
    entradas = await _pavimentos(pavimentos, sessao)

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
            importacao = importar(temporario, Catalogo(unidades_excluidas=excluidas))
        except ErroDeLeitura as erro:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)
            )
    finally:
        temporario.unlink(missing_ok=True)

    clinicas = para_clinicas(importacao.demandas)

    resultado = None
    if clinicas and entradas:
        dominio = tuple(
            PavimentoDominio(id=i, nome=e.nome_completo, capacidade=e.capacidade)
            for i, e in enumerate(entradas, start=1)
        )
        resultado = SolverHeuristico().resolver(
            EntradaAlocacao(clinicas=clinicas, pavimentos=dominio)
        )

    # O catálogo aprende as unidades vistas — inclusive as que não participam.
    catalogo = CatalogoRepository(sessao)
    await catalogo.aprender_unidades([c.nome for c in clinicas] + sorted(excluidas))

    repo = AlocacaoRepository(sessao)
    cenario = await repo.criar(
        nome=nome_cenario,
        clinicas=clinicas,
        slots=importacao.slots,
        demandas=importacao.demandas,
        pavimentos=entradas,
        resultado=resultado,
        unidades_excluidas=tuple(sorted(excluidas)),
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
# Auxiliares
# ---------------------------------------------------------------------------


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
                "nome": unidade.unidade_nome,
                "participa": unidade.participa,
                "pavimento": destino.nome_completo if destino else None,
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
        if await catalogo.semear_pavimentos():
            await sessao.commit()
        return tuple(
            PavimentoEntrada(
                bloco=p.bloco,
                nome=p.nome,
                padrao_1est=p.padrao_1est,
                padrao_2est=p.padrao_2est,
                esp_1est=p.esp_1est,
                esp_2est=p.esp_2est,
                fechada=p.fechada,
            )
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
