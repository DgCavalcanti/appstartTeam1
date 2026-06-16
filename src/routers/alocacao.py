"""
Router SAA — Alocações

Endpoints MVP (sem alocação automática):
  GET  /api/alocacoes              — listar com filtros
  POST /api/alocacoes/ajustar      — ajuste manual
  GET  /api/alocacoes/historico    — histórico de ajustes

O endpoint POST /api/alocacoes/automatica NÃO existe neste MVP.
O motor alocacao_engine.py está preservado como módulo futuro/experimental
e não é importado aqui.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from src.controllers.alocacao_controller import AlocacaoController
from src.models.schemas import (
    Alocacao,
    AjusteAlocacaoRequest,
    AjusteAlocacaoResponse,
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
