"""Router SAA — Dashboard (GET /api/dashboard/resumo, GET /api/dashboard/conflitos)"""
from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.dashboard_controller import DashboardController
from src.models.schemas import Conflito, DashboardResumo
from src.providers.implementations.alocacao_saa_csv_provider import AlocacaoSaaCsvProvider
from src.providers.implementations.grade_aghu_dashboard_provider import GradeAghuDashboardProvider
from src.providers.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.providers.implementations.sala_csv_provider import SalaCsvProvider
from src.routers.aghu import _GRADES_PATH
from src.routers.alocacao import _ALOCACOES_PATH, _DB_PATH
from src.routers.restricao import _RESTRICOES_PATH
from src.routers.sala import _SALAS_PATH

router = APIRouter(prefix="/api/dashboard", tags=["SAA — Dashboard"])


def get_dashboard_controller() -> DashboardController:
    return DashboardController(
        grade_provider=GradeAghuDashboardProvider(caminho=_GRADES_PATH),
        sala_provider=SalaCsvProvider(caminho=_SALAS_PATH),
        restricao_provider=RestricaoCsvProvider(caminho=_RESTRICOES_PATH),
        alocacao_provider=AlocacaoSaaCsvProvider(
            caminho_alocacoes=_ALOCACOES_PATH,
            caminho_db=_DB_PATH,
        ),
    )


@router.get("/resumo", response_model=DashboardResumo, summary="Resumo do dashboard")
def resumo(controller: DashboardController = Depends(get_dashboard_controller)):
    try:
        return controller.resumo()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/conflitos", response_model=list[Conflito], summary="Listar conflitos detectados")
def conflitos(
    dia_semana: str | None = Query(None),
    turno: str | None = Query(None),
    especialidade: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    controller: DashboardController = Depends(get_dashboard_controller),
):
    try:
        todos = controller.conflitos(dia_semana=dia_semana, turno=turno, especialidade=especialidade)
        return todos[offset: offset + limit]
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
