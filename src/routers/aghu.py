"""Router AGHU — endpoints de análise e consulta dos dados reais do AGHU.

Nunca retorna centenas de milhares de linhas brutas. Toda consulta usa
paginação ou agrega os dados no backend antes de responder.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, status

from src.models.schemas import (
    CapacidadeResumo,
    GradeAghu,
    ImportacaoResultado,
    QualidadeDados,
    ResumoEspecialidade,
    ResumoDiaTurno,
    Consulta,
)
from src.providers.implementations.grade_aghu_csv_provider import GradeAghuCsvProvider
from src.providers.implementations.consulta_aghu_csv_provider import ConsultaAghuCsvProvider
from src.services.consulta_service import ConsultaService

router = APIRouter(prefix="/api/aghu", tags=["AGHU — Dados Reais"])

_GRADES_PATH = Path(os.getenv("AGHU_GRADES_PATH", "data/vw_grades.csv"))
_CONSULTAS_PATH = Path(os.getenv("AGHU_CONSULTAS_PATH", "data/vw_consultas_2026.csv"))


def _service() -> ConsultaService:
    return ConsultaService(
        provider_grades=GradeAghuCsvProvider(caminho=_GRADES_PATH),
        provider_consultas=ConsultaAghuCsvProvider(caminho=_CONSULTAS_PATH),
    )


def _grade_provider() -> GradeAghuCsvProvider:
    return GradeAghuCsvProvider(caminho=_GRADES_PATH)


def _handle_not_found(e: FileNotFoundError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_424_FAILED_DEPENDENCY,
        detail=str(e),
    )


def _handle_invalid(e: ValueError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=str(e),
    )


# ── Grades AGHU ───────────────────────────────────────────────────────────────

@router.get("/grades", response_model=list[GradeAghu], summary="Listar grades AGHU")
def listar_grades_aghu(
    especialidade: str | None = Query(None),
    turno: str | None = Query(None),
    dia_semana: str | None = Query(None),
    situacao_grade: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
):
    try:
        provider = _grade_provider()
        grades = provider.listar_grades()
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)

    if especialidade:
        grades = [g for g in grades if especialidade.upper() in g.especialidade.upper()]
    if turno:
        grades = [g for g in grades if turno.upper() in g.turno.upper()]
    if dia_semana:
        grades = [g for g in grades if dia_semana.upper() in g.dia_semana.upper()]
    if situacao_grade:
        grades = [g for g in grades if situacao_grade.upper() in g.situacao_grade.upper()]

    return grades[offset: offset + limit]


@router.get("/grades/resumo", response_model=ImportacaoResultado, summary="Resumo da importação de grades AGHU")
def resumo_grades_aghu():
    try:
        provider = _grade_provider()
        r = provider.resumo_importacao()
        return ImportacaoResultado(
            arquivo=r["arquivo"],
            linhas_lidas=r["linhas_lidas"],
            linhas_validas=r["linhas_validas"],
            registros_unicos=r["grades_unicas"],
            avisos=r["avisos"],
        )
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


# ── Consultas AGHU ────────────────────────────────────────────────────────────

@router.get("/consultas", response_model=list[Consulta], summary="Listar consultas AGHU (paginado)")
def listar_consultas_aghu(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    especialidade: str | None = Query(None),
    unidade_funcional: str | None = Query(None),
    profissional: str | None = Query(None),
    turno: str | None = Query(None),
    dia_semana: str | None = Query(None),
    situacao_consulta: str | None = Query(None),
    apenas_excedentes: bool = Query(False),
):
    try:
        svc = _service()
        return svc.listar_consultas(
            limit=limit,
            offset=offset,
            especialidade=especialidade,
            unidade_funcional=unidade_funcional,
            profissional=profissional,
            turno=turno,
            dia_semana=dia_semana,
            situacao_consulta=situacao_consulta,
            apenas_excedentes=apenas_excedentes,
        )
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


@router.get("/consultas/resumo", response_model=ImportacaoResultado, summary="Resumo da importação de consultas")
def resumo_consultas_aghu():
    try:
        provider = ConsultaAghuCsvProvider(caminho=_CONSULTAS_PATH)
        r = provider.resumo_importacao()
        return ImportacaoResultado(
            arquivo=r["arquivo"],
            linhas_lidas=r["linhas_lidas"],
            linhas_validas=r["linhas_validas"],
            registros_unicos=r["registros_unicos"],
            avisos=r["avisos"],
        )
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


@router.get(
    "/consultas/por-especialidade",
    response_model=list[ResumoEspecialidade],
    summary="Resumo de consultas agrupado por especialidade",
)
def consultas_por_especialidade():
    try:
        svc = _service()
        return svc.por_especialidade()
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


@router.get(
    "/consultas/por-dia-turno",
    response_model=list[ResumoDiaTurno],
    summary="Resumo de consultas agrupado por dia da semana e turno",
)
def consultas_por_dia_turno():
    try:
        svc = _service()
        return svc.por_dia_turno()
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


@router.get(
    "/consultas/excedentes",
    response_model=list[Consulta],
    summary="Listar consultas excedentes",
)
def consultas_excedentes(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    try:
        svc = _service()
        return svc.listar_excedentes(limit=limit, offset=offset)
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


# ── Capacidade e qualidade ────────────────────────────────────────────────────

@router.get(
    "/capacidade/resumo",
    response_model=CapacidadeResumo,
    summary="Resumo de capacidade ambulatorial",
)
def capacidade_resumo():
    try:
        svc = _service()
        return svc.resumo_capacidade()
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)


@router.get(
    "/qualidade-dados",
    response_model=QualidadeDados,
    summary="Painel de qualidade dos dados importados",
)
def qualidade_dados():
    try:
        svc = _service()
        return svc.qualidade_dados()
    except FileNotFoundError as e:
        raise _handle_not_found(e)
    except ValueError as e:
        raise _handle_invalid(e)
