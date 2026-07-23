"""Router SAA — Grades (GET /api/grades, GET /api/grades/{grade_id})"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.models.schemas import Grade
from src.repositories.implementations.grade_aghu_dashboard_provider import GradeAghuDashboardProvider
from src.repositories.interfaces.grade_provider_interface import GradeProviderInterface
from src.services.grade_service import GradeService
from src.routers.aghu import _GRADES_PATH

router = APIRouter(prefix="/api/grades", tags=["SAA — Grades"])


def get_grade_provider() -> GradeProviderInterface:
    return GradeAghuDashboardProvider(caminho=_GRADES_PATH)


def get_grade_service(
    provider: GradeProviderInterface = Depends(get_grade_provider),
) -> GradeService:
    return GradeService(provider)


@router.get("", response_model=list[Grade], summary="Listar grades")
def listar_grades(
    especialidade: str | None = Query(None),
    dia_semana: str | None = Query(None),
    turno: str | None = Query(None),
    service: GradeService = Depends(get_grade_service),
):
    try:
        return service.listar_grades(especialidade=especialidade, dia_semana=dia_semana, turno=turno)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/{grade_id}", response_model=Grade, summary="Buscar grade por ID")
def buscar_grade(
    grade_id: str,
    service: GradeService = Depends(get_grade_service),
):
    try:
        grade = service.buscar_grade(grade_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Grade '{grade_id}' não encontrada.")
    return grade
