"""
importacao.py — Router da etapa 1 (importação) e da simulação de alocação.

Fatia vertical do fluxo novo: recebe a exportação do AGHU, roda o pipeline de
tratamento e, com as capacidades informadas, executa o motor de alocação.

Este router é a pré-visualização: nada é gravado. Para persistir o resultado
como um cenário do histórico, use POST /api/cenarios.
"""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import (
    NUM_TURNOS,
    TURNOS,
    Pavimento,
    capacidade_em_estacoes,
)
from src.domain.importacao import Catalogo, importar, para_clinicas
from src.domain.importacao.leitor import ErroDeLeitura
from src.repositories.catalogo_repository import PAVIMENTOS_SEMENTE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/importacao", tags=["Importação"])


#: Panorama de salas usado quando o gestor ainda não editou a etapa 3.
#: Espelha a semente do catálogo: 9 pavimentos, 231 estações por turno.
PAVIMENTOS_PADRAO: tuple[dict, ...] = PAVIMENTOS_SEMENTE

#: Rótulos dos 10 turnos, na ordem canônica dos vetores de demanda.
ROTULOS_TURNOS: tuple[dict, ...] = tuple(
    {"dia": dia, "periodo": periodo} for dia, periodo in TURNOS
)

EXTENSOES_ACEITAS = {".csv", ".xlsx", ".xls"}


@router.post(
    "",
    summary="Importar grades do AGHU e simular a alocação",
    description=(
        "Recebe a exportação do AGHU, roda o pipeline de tratamento (etapa 1) e "
        "executa o motor de alocação sobre o panorama de salas informado. "
        "Nada é persistido."
    ),
)
async def importar_e_simular(
    arquivo: UploadFile = File(..., description="Exportação do AGHU (.csv ou .xlsx)"),
    pavimentos: str | None = Form(
        None,
        description=(
            'JSON com as contagens de salas por pavimento: '
            '[{"bloco": "...", "nome": "...", "padrao_1est": 8, "padrao_2est": 9, '
            '"esp_1est": 4, "esp_2est": 2}]. A capacidade é derivada.'
        ),
    ),
    unidades_excluidas: str | None = Form(
        None, description='JSON: ["ALMOXARIFADO", ...] — unidades que não participam'
    ),
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

    catalogo = Catalogo(unidades_excluidas=_lista(unidades_excluidas, "unidades_excluidas"))
    lista_pavimentos = _pavimentos(pavimentos)

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
            resultado = importar(temporario, catalogo)
        except ErroDeLeitura as erro:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)
            )
    finally:
        temporario.unlink(missing_ok=True)

    clinicas = para_clinicas(resultado.demandas)

    alocacao = None
    if clinicas and lista_pavimentos:
        alocacao = SolverHeuristico().resolver(
            EntradaAlocacao(clinicas=clinicas, pavimentos=lista_pavimentos)
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
        "clinicas": [
            {
                "id": c.id,
                "nome": c.nome,
                "demanda": list(c.demanda),
                "total": c.total,
                "pico": c.pico,
            }
            for c in clinicas
        ],
        "unidades_novas": list(resultado.unidades_novas),
        "slots_em_revisao": [
            {
                "profissional": s.profissional,
                "unidade": s.unidade,
                "dia": s.dia,
                "periodo": s.periodo,
            }
            for s in resultado.slots
            if s.revisar
        ],
        "alocacao": _serializar_alocacao(alocacao, lista_pavimentos),
    }


def _serializar_alocacao(alocacao, pavimentos: tuple[Pavimento, ...]) -> dict | None:
    if alocacao is None:
        return None

    nomes = {p.id: p.nome for p in pavimentos}
    return {
        "total_alocado": alocacao.total_alocado,
        "total_nao_alocado": alocacao.total_nao_alocado,
        "por_clinica": [
            {
                "clinica_id": r.clinica_id,
                "nome": r.nome,
                "pavimento_id": r.pavimento_id,
                "pavimento": nomes.get(r.pavimento_id, "?"),
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


def _pavimentos(bruto: str | None) -> tuple[Pavimento, ...]:
    """
    Converte as contagens de salas enviadas pela etapa 3 em pavimentos do motor.

    A capacidade é sempre derivada das contagens — nunca aceita pronta do
    cliente — para não divergir do número que o gestor edita.
    """
    if not bruto:
        entradas = PAVIMENTOS_PADRAO
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
        return tuple(
            Pavimento(
                id=i,
                nome=str(
                    entrada.get("nome_completo")
                    or " — ".join(
                        parte
                        for parte in (entrada.get("bloco"), entrada.get("nome"))
                        if parte
                    )
                    or f"Pavimento {i}"
                ),
                capacidade=capacidade_em_estacoes(
                    padrao_1est=int(entrada.get("padrao_1est", 0)),
                    padrao_2est=int(entrada.get("padrao_2est", 0)),
                    esp_1est=int(entrada.get("esp_1est", 0)),
                    esp_2est=int(entrada.get("esp_2est", 0)),
                ),
            )
            for i, entrada in enumerate(entradas, start=1)
        )
    except (AttributeError, TypeError, ValueError) as erro:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pavimento inválido: {erro}",
        )


@router.get(
    "/padroes",
    summary="Panorama de salas padrão",
    description="Capacidades usadas quando o gestor ainda não editou a etapa 3.",
)
def obter_padroes():
    return {
        "pavimentos": list(PAVIMENTOS_PADRAO),
        "turnos": ROTULOS_TURNOS,
        "num_turnos": NUM_TURNOS,
    }
