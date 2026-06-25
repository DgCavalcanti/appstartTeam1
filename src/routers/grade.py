"""Router SAA — Grades

  GET  /api/grades                       — listar com filtros
  GET  /api/grades/{grade_id}             — buscar por ID
  POST /api/grades/remover-duplicadas     — verificar/normalizar duplicatas
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.grade_controller import GradeController
from src.models.schemas import Grade, RemocaoGradesDuplicadasResultado
from src.providers.implementations.grade_aghu_dashboard_provider import GradeAghuDashboardProvider
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface
from src.routers.aghu import _GRADES_PATH

router = APIRouter(prefix="/api/grades", tags=["SAA — Grades"])


def get_grade_provider() -> GradeProviderInterface:
    return GradeAghuDashboardProvider(caminho=_GRADES_PATH)


def get_grade_controller(
    provider: GradeProviderInterface = Depends(get_grade_provider),
) -> GradeController:
    return GradeController(provider)


@router.get("", response_model=list[Grade], summary="Listar grades")
def listar_grades(
    especialidade: str | None = Query(None),
    dia_semana: str | None = Query(None),
    turno: str | None = Query(None),
    controller: GradeController = Depends(get_grade_controller),
):
    try:
        return controller.listar_grades(especialidade=especialidade, dia_semana=dia_semana, turno=turno)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/{grade_id}", response_model=Grade, summary="Buscar grade por ID")
def buscar_grade(
    grade_id: str,
    controller: GradeController = Depends(get_grade_controller),
):
    try:
        grade = controller.buscar_grade(grade_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Grade '{grade_id}' não encontrada.")
    return grade


@router.post(
    "/remover-duplicadas",
    response_model=RemocaoGradesDuplicadasResultado,
    summary="Verificar e normalizar grades duplicadas",
    description=(
        "O SAA exige que cada grade (grade_id + dia_semana + turno) seja única. "
        "A normalização já acontece automaticamente em toda listagem — este "
        "endpoint recalcula e confirma o resultado, sem apagar nada de "
        "vw_grades.csv (os relatórios de capacidade/qualidade do módulo "
        "'AGHU: Dados Reais' continuam usando todas as linhas originais)."
    ),
)
def remover_grades_duplicadas(
    provider: GradeProviderInterface = Depends(get_grade_provider),
):
    if not isinstance(provider, GradeAghuDashboardProvider):
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Operação não suportada para este provider de grades.",
        )
    try:
        total_brutas, total_unicas = provider.relatorio_duplicadas()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    duplicadas = total_brutas - total_unicas
    if duplicadas > 0:
        mensagem = (
            f"{duplicadas} linha(s) duplicada(s) detectada(s) em vw_grades.csv "
            f"(mesma grade + dia + turno, diferindo só pela condição de "
            f"atendimento). O SAA já exibe apenas as {total_unicas} grade(s) "
            f"única(s) — nenhuma sala alocada foi afetada."
        )
    else:
        mensagem = f"Nenhuma grade duplicada encontrada. {total_unicas} grade(s) única(s)."

    return RemocaoGradesDuplicadasResultado(
        total_linhas_brutas=total_brutas,
        total_grades_unicas=total_unicas,
        duplicadas_normalizadas=duplicadas,
        mensagem=mensagem,
    )
