"""
importacao.py — Pré-visualização da importação (etapa 1).

Recebe a exportação do AGHU, roda o pipeline de tratamento e simula a alocação
sobre o panorama de salas informado. Nada é persistido — é a prévia que o gestor
vê antes de salvar o cenário via POST /api/cenarios.

O filtro de unidades vem do catálogo: quem participa do ambulatório está na
lista de referência, não numa heurística de nome.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import NamedTuple

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import TURNOS, Pavimento, capacidade_em_estacoes
from src.domain.importacao import Catalogo, importar, normalizar, para_clinicas
from src.domain.importacao.leitor import ErroDeLeitura
from src.repositories import CatalogoRepository, PavimentoEntrada
from src.resources.database import get_app_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/importacao", tags=["Importação"])

#: Rótulos dos 10 turnos, na ordem canônica dos vetores de demanda.
ROTULOS_TURNOS: tuple[dict, ...] = tuple(
    {"dia": dia, "periodo": periodo} for dia, periodo in TURNOS
)

EXTENSOES_ACEITAS = {".csv", ".xlsx", ".xls"}


@router.post(
    "",
    summary="Importar grades do AGHU e simular a alocação",
    description=(
        "Pré-visualização: roda o pipeline de tratamento e simula o motor. "
        "Nada é gravado. Para persistir como cenário, use POST /api/cenarios."
    ),
)
async def importar_e_simular(
    arquivo: UploadFile = File(..., description="Exportação do AGHU (.csv ou .xlsx)"),
    pavimentos: str | None = Form(
        None,
        description=(
            'JSON com as contagens de salas por pavimento. Se ausente, usa o '
            'mapa do HC do catálogo.'
        ),
    ),
    unidades_excluidas: str | None = Form(
        None,
        description=(
            'JSON: ["ALMOXARIFADO", ...]. Se ausente, as exclusões vêm do '
            'catálogo (unidades que não participam do ambulatório).'
        ),
    ),
    sessao: AsyncSession = Depends(get_app_db_session),
):
    nome_original = arquivo.filename or "grades.csv"
    sufixo = Path(nome_original).suffix.lower()
    if sufixo not in EXTENSOES_ACEITAS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"extensão não suportada: {sufixo or '(nenhuma)'}. "
                f"Aceitos: {sorted(EXTENSOES_ACEITAS)}"
            ),
        )

    catalogo = CatalogoRepository(sessao)
    await catalogo.semear_referencia()
    lista_pavimentos = await _pavimentos(pavimentos, catalogo)

    # As exclusões: a escolha explícita do gestor, se veio; senão o padrão do
    # catálogo — a lista real de unidades que não participam do ambulatório.
    if unidades_excluidas is None:
        excluidas_norm = await catalogo.unidades_excluidas()
    else:
        excluidas_norm = frozenset(
            _normalizar_nomes(_lista(unidades_excluidas, "unidades_excluidas"))
        )

    conteudo = await arquivo.read()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="o arquivo enviado está vazio",
        )

    # `ler_planilha` trabalha sobre um caminho — grava num temporário que é
    # removido logo em seguida. As linhas brutas não persistem em lugar nenhum.
    temporario = Path(tempfile.gettempdir()) / f"saa_upload_{id(conteudo)}{sufixo}"
    try:
        temporario.write_bytes(conteudo)
        try:
            resultado = importar(temporario, Catalogo(unidades_excluidas=excluidas_norm))
        except ErroDeLeitura as erro:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)
            )
    finally:
        temporario.unlink(missing_ok=True)

    # `unidades_vistas` traz todas as unidades do arquivo (antes de filtrar), na
    # grafia original. Uma unidade participa quando sua forma normalizada não
    # está no conjunto de exclusões.
    participa = {
        nome: normalizar(nome) not in excluidas_norm
        for nome in resultado.unidades_vistas
    }

    clinicas = para_clinicas(resultado.demandas)

    dominios = tuple(p.dominio for p in lista_pavimentos)
    alocacao = None
    if clinicas and dominios:
        alocacao = SolverHeuristico().resolver(
            EntradaAlocacao(clinicas=clinicas, pavimentos=dominios)
        )

    relatorio = resultado.relatorio
    return {
        "arquivo": nome_original,
        "turnos": ROTULOS_TURNOS,
        "relatorio": {
            "linhas_brutas": relatorio.linhas_brutas,
            "linhas_apos_filtros": relatorio.linhas_apos_filtros,
            "total_slots": relatorio.total_slots,
            "total_demandas": relatorio.total_demandas,
            "percentual_apos_filtros": round(relatorio.percentual_apos_filtros, 1),
            "percentual_slots": round(relatorio.percentual_slots, 1),
            "percentual_demandas": round(relatorio.percentual_demandas, 1),
            "descartadas_por_situacao": relatorio.descartadas_por_situacao,
            "descartadas_por_condicao": relatorio.descartadas_por_condicao,
            "descartadas_por_unidade": relatorio.descartadas_por_unidade,
            "descartadas_por_dia": relatorio.descartadas_por_dia,
            "descartadas_por_noite": relatorio.descartadas_por_noite,
            "slots_em_revisao": relatorio.slots_em_revisao,
        },
        # Todas as unidades do arquivo, com a participação padrão — é o que a
        # etapa 2 lista como caixas de seleção.
        "unidades": [
            {
                "nome": nome,
                "participa": participa[nome],
                "nova": nome in resultado.unidades_novas,
            }
            for nome in sorted(resultado.unidades_vistas)
        ],
        "clinicas": [
            {"id": c.id, "nome": c.nome, "demanda": list(c.demanda), "total": c.total, "pico": c.pico}
            for c in clinicas
        ],
        "unidades_novas": list(resultado.unidades_novas),
        "slots_em_revisao": [
            {"profissional": s.profissional, "unidade": s.unidade, "dia": s.dia, "periodo": s.periodo}
            for s in resultado.slots
            if s.revisar
        ],
        "alocacao": _serializar_alocacao(alocacao, lista_pavimentos),
    }


def _serializar_alocacao(
    alocacao, pavimentos: tuple[PavimentoPreview, ...]
) -> dict | None:
    if alocacao is None:
        return None

    meta = {p.dominio.id: p for p in pavimentos}
    return {
        "total_alocado": alocacao.total_alocado,
        "total_nao_alocado": alocacao.total_nao_alocado,
        "por_clinica": [
            {
                "clinica_id": r.clinica_id,
                "nome": r.nome,
                "pavimento_id": r.pavimento_id,
                # Bloco e andar separados para colunas/filtros; completo p/ tooltip.
                "bloco": meta[r.pavimento_id].bloco if r.pavimento_id in meta else None,
                "pavimento": meta[r.pavimento_id].pavimento if r.pavimento_id in meta else None,
                "pavimento_completo": meta[r.pavimento_id].dominio.nome if r.pavimento_id in meta else "?",
                "alocado": list(r.alocado),
                "nao_alocado": list(r.nao_alocado),
                "total_alocado": r.total_alocado,
                "total_nao_alocado": r.total_nao_alocado,
            }
            for r in alocacao.por_clinica
        ],
        "por_pavimento": [
            {
                "pavimento_id": o.pavimento_id,
                "nome": o.nome,
                "capacidade": o.capacidade,
                "ocupacao": list(o.ocupacao),
                "demanda": list(o.demanda),
                "ocupacao_media": round(100 * o.ocupacao_media, 1),
                "ocupacao_pico": round(100 * o.ocupacao_pico, 1),
                "clinicas": sum(
                    1 for r in alocacao.por_clinica if r.pavimento_id == o.pavimento_id
                ),
            }
            for o in alocacao.por_pavimento
        ],
    }


def _normalizar_nomes(nomes) -> list[str]:
    """As chaves que o pipeline compara são as formas normalizadas dos nomes."""
    return [normalizar(n) for n in nomes]


def _lista(bruto: str | None, campo: str) -> list[str]:
    if not bruto:
        return []
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
    return [str(v) for v in valores]


class PavimentoPreview(NamedTuple):
    """Pavimento do motor mais o bloco e o andar, para a tela separar as colunas."""

    dominio: Pavimento
    bloco: str
    pavimento: str


async def _pavimentos(
    bruto: str | None, catalogo: CatalogoRepository
) -> tuple[PavimentoPreview, ...]:
    """
    Converte as contagens de salas em pavimentos do motor.

    Sem contagens do cliente, usa o mapa do HC do catálogo. A capacidade é
    sempre derivada das contagens — nunca aceita pronta.
    """
    if not bruto:
        await catalogo.semear_referencia()
        entradas = [
            {
                "bloco": p.bloco,
                "nome": p.nome,
                "padrao_1est": p.padrao_1est,
                "padrao_2est": p.padrao_2est,
                "esp_1est": p.esp_1est,
                "esp_2est": p.esp_2est,
            }
            for p in await catalogo.listar_pavimentos()
        ]
    else:
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
        preview = []
        for i, entrada in enumerate(entradas, start=1):
            bloco = str(entrada.get("bloco") or "")
            pavimento = str(entrada.get("nome") or f"Pavimento {i}")
            completo = (
                entrada.get("nome_completo")
                or " — ".join(p for p in (bloco, pavimento) if p)
                or f"Pavimento {i}"
            )
            preview.append(
                PavimentoPreview(
                    dominio=Pavimento(
                        id=i,
                        nome=str(completo),
                        capacidade=capacidade_em_estacoes(
                            padrao_1est=int(entrada.get("padrao_1est", 0)),
                            padrao_2est=int(entrada.get("padrao_2est", 0)),
                            esp_1est=int(entrada.get("esp_1est", 0)),
                            esp_2est=int(entrada.get("esp_2est", 0)),
                        ),
                    ),
                    bloco=bloco,
                    pavimento=pavimento,
                )
            )
        return tuple(preview)
    except (AttributeError, TypeError, ValueError) as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pavimento inválido: {erro}",
        )
