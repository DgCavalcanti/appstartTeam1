from src.models.schemas import Grade
from src.repositories.interfaces.grade_provider_interface import GradeProviderInterface


class GradeService:

    def __init__(self, provider: GradeProviderInterface) -> None:
        self._provider = provider

    def listar_grades(
        self,
        especialidade: str | None = None,
        dia_semana: str | None = None,
        turno: str | None = None,
    ) -> list[Grade]:
        grades = self._provider.listar_grades()
        if especialidade:
            grades = [g for g in grades if g.especialidade.lower() == especialidade.lower()]
        if dia_semana:
            grades = [g for g in grades if g.dia_semana.lower() == dia_semana.lower()]
        if turno:
            grades = [g for g in grades if g.turno.lower() == turno.lower()]
        return grades

    def buscar_grade(self, grade_id: str) -> Grade | None:
        return self._provider.buscar_grade(grade_id)
