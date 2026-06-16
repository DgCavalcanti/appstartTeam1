"""Adapter que expõe a grade REAL do AGHU (vw_grades.csv) através do
contrato `GradeProviderInterface` usado pelo módulo SAA (Dashboard,
Grades, Alocações).

Antes, esses três pontos do sistema liam um CSV simplificado e fictício
(`data/grades.csv`). Este adapter substitui essa fonte: ele reaproveita
o `GradeAghuCsvProvider` (mesmo provider usado pelas telas "AGHU: Dados
Reais") e converte cada `GradeAghu` para o modelo `Grade` que o módulo
SAA já sabe consumir — sem precisar alterar controllers nem services.

Mapeamento Grade <- GradeAghu:
    id                    <- grade_id
    especialidade         <- especialidade
    profissional          <- profissional
    dia_semana            <- dia_semana
    turno                 <- turno
    qtd_salas_necessarias <- qtd_salas_necessarias (fixo em 1 — ver regra
                              de negócio em grade_aghu_csv_provider.py)
"""
from __future__ import annotations

from pathlib import Path

from src.models.schemas import Grade, GradeAghu
from src.providers.implementations.grade_aghu_csv_provider import GradeAghuCsvProvider
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface


class GradeAghuDashboardProvider(GradeProviderInterface):
    """Adapta GradeAghuCsvProvider (formato real AGHU) para o contrato Grade do SAA."""

    def __init__(self, caminho: Path = Path("data/vw_grades.csv")) -> None:
        self._provider = GradeAghuCsvProvider(caminho=caminho)

    def listar_grades(self) -> list[Grade]:
        return [self._adaptar(g) for g in self._provider.listar_grades()]

    def buscar_grade(self, grade_id: str) -> Grade | None:
        g = self._provider.buscar_grade(grade_id)
        return self._adaptar(g) if g else None

    @staticmethod
    def _adaptar(g: GradeAghu) -> Grade:
        return Grade(
            id=g.grade_id,
            especialidade=g.especialidade,
            profissional=g.profissional,
            dia_semana=g.dia_semana,
            turno=g.turno,
            qtd_salas_necessarias=g.qtd_salas_necessarias,
        )
