"""
Router SAA — Alocações

Endpoints:
  GET  /api/alocacoes              — listar com filtros
  POST /api/alocacoes              — criar a 1ª alocação de uma grade
  POST /api/alocacoes/automatica   — alocação automática por dia/turno
  POST /api/alocacoes/ajustar      — ajuste manual (grade já alocada)
  GET  /api/alocacoes/historico    — histórico de ajustes

"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.controllers.alocacao_controller import AlocacaoController
from src.models.schemas import (
    Alocacao,
    AlocacaoAutomaticaRequest,
    AlocacaoAutomaticaResponse,
    AjusteAlocacaoRequest,
    AjusteAlocacaoResponse,
    CriarAlocacaoRequest,
    CriarAlocacaoResponse,
    HistoricoAjuste,
)
from src.providers.implementations.alocacao_saa_csv_provider import AlocacaoSaaCsvProvider
from src.providers.implementations.grade_aghu_dashboard_provider import GradeAghuDashboardProvider
from src.providers.implementations.historico_sqlite_provider import HistoricoSqliteProvider
from src.providers.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.providers.implementations.sala_csv_provider import SalaCsvProvider
from src.routers.aghu import _GRADES_PATH
from src.routers.sala import _SALAS_PATH
from src.routers.restricao import _RESTRICOES_PATH

router = APIRouter(prefix="/api/alocacoes", tags=["SAA — Alocações"])

# Mesmo caminho usado pela escrita em POST /api/importacao/alocacoes.
_ALOCACOES_PATH = Path(os.getenv("SAA_ALOCACOES_PATH", "data/alocacoes.csv"))
_DB_PATH = Path("data/saa.db")


def get_alocacao_controller() -> AlocacaoController:
    return AlocacaoController(
        alocacao_provider=AlocacaoSaaCsvProvider(
            caminho_alocacoes=_ALOCACOES_PATH,
            caminho_db=_DB_PATH,
        ),
        grade_provider=GradeAghuDashboardProvider(caminho=_GRADES_PATH),
        sala_provider=SalaCsvProvider(caminho=_SALAS_PATH),
        restricao_provider=RestricaoCsvProvider(caminho=_RESTRICOES_PATH),
        historico_provider=HistoricoSqliteProvider(caminho_db=_DB_PATH),
    )


@router.get("", response_model=list[Alocacao], summary="Listar alocações")
def listar_alocacoes(
    dia_semana: str | None = Query(None, description="Filtrar por dia da semana"),
    turno: str | None = Query(None, description="Filtrar por turno"),
    controller: AlocacaoController = Depends(get_alocacao_controller),
):
    try:
        return controller.listar_alocacoes(dia_semana=dia_semana, turno=turno)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.post(
    "",
    response_model=CriarAlocacaoResponse,
    summary="Criar alocação (1ª sala de uma grade)",
    description=(
        "Aloca uma sala para uma grade que ainda não possui nenhuma alocação. "
        "Para trocar a sala de uma grade já alocada, use POST /api/alocacoes/ajustar. "
        "Exige justificativa quando a sala escolhida gera conflito crítico ou operacional."
    ),
)
def criar_alocacao(
    req: CriarAlocacaoRequest,
    x_usuario: str | None = Header(None, alias="X-Usuario"),
    controller: AlocacaoController = Depends(get_alocacao_controller),
):
    usuario = x_usuario or "anonimo"
    try:
        return controller.criar_alocacao(req, usuario=usuario)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))


@router.post(
    "/automatica",
    response_model=AlocacaoAutomaticaResponse,
    summary="Executar alocacao automatica",
    description=(
        "Gera alocacoes automaticamente para um dia/turno usando o motor do SAA. "
        "Por padrao, preserva alocacoes existentes; use sobrescrever=true para "
        "recalcular ocorrencias ja alocadas."
    ),
)
def alocar_automaticamente(
    req: AlocacaoAutomaticaRequest,
    x_usuario: str | None = Header(None, alias="X-Usuario"),
    controller: AlocacaoController = Depends(get_alocacao_controller),
):
    usuario = x_usuario or "anonimo"
    try:
        return controller.alocar_automaticamente(req, usuario=usuario)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))


@router.post(
    "/ajustar",
    response_model=AjusteAlocacaoResponse,
    summary="Ajustar alocação manualmente",
    description=(
        "Altera a sala de uma alocação existente. "
        "Exige justificativa quando a nova configuração gera conflito crítico ou operacional."
    ),
)
def ajustar_alocacao(
    req: AjusteAlocacaoRequest,
    x_usuario: str | None = Header(None, alias="X-Usuario"),
    controller: AlocacaoController = Depends(get_alocacao_controller),
):
    usuario = x_usuario or "anonimo"
    try:
        return controller.ajustar_alocacao(req, usuario=usuario)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))


@router.get(
    "/historico",
    response_model=list[HistoricoAjuste],
    summary="Histórico de ajustes manuais",
)
def listar_historico(
    controller: AlocacaoController = Depends(get_alocacao_controller),
):
    return controller.listar_historico()
