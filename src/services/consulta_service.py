"""Serviço de consultas AGHU.

Orquestra leituras do ConsultaAghuCsvProvider e aplica agregações.
"""
from __future__ import annotations


from src.models.schemas import (
    CapacidadeResumo,
    Consulta,
    QualidadeDados,
    ResumoEspecialidade,
    ResumoDiaTurno,
)
from src.providers.implementations.grade_aghu_csv_provider import GradeAghuCsvProvider
from src.providers.implementations.consulta_aghu_csv_provider import ConsultaAghuCsvProvider
from src.services.capacidade_service import (
    calcular_resumo,
    resumo_por_especialidade,
    resumo_por_dia_turno,
)
from src.services.qualidade_dados_service import analisar_qualidade


class ConsultaService:

    def __init__(
        self,
        provider_grades: GradeAghuCsvProvider,
        provider_consultas: ConsultaAghuCsvProvider,
    ) -> None:
        self._grades = provider_grades
        self._consultas = provider_consultas

    def resumo_capacidade(self) -> CapacidadeResumo:
        grades = self._grades.listar_grades()
        linhas = self._consultas.listar_linhas_brutas()
        return calcular_resumo(grades, linhas)

    def por_especialidade(self) -> list[ResumoEspecialidade]:
        linhas = self._consultas.listar_linhas_brutas()
        return resumo_por_especialidade(linhas)

    def por_dia_turno(self) -> list[ResumoDiaTurno]:
        linhas = self._consultas.listar_linhas_brutas()
        return resumo_por_dia_turno(linhas)

    def qualidade_dados(self) -> QualidadeDados:
        grades = self._grades.listar_grades()
        linhas = self._consultas.listar_linhas_brutas()
        return analisar_qualidade(grades, linhas)

    def listar_consultas(self, **kwargs) -> list[Consulta]:
        return self._consultas.listar_consultas(**kwargs)

    def listar_excedentes(self, limit: int = 100, offset: int = 0) -> list[Consulta]:
        return self._consultas.listar_consultas(apenas_excedentes=True, limit=limit, offset=offset)
