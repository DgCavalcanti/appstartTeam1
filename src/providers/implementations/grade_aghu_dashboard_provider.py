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

Deduplicação (regra de negócio do SAA — grades devem ser únicas):
    vw_grades.csv pode ter várias linhas para o mesmo (grade_id, dia_semana,
    turno) — uma por Condicao_De_Atendimento (RETORNO, CONSULTA PRIMEIRA
    VEZ, INTERCONSULTA, etc.), cada uma com sua própria Quantidade_Vagas.
    Essas linhas são dados reais e legítimos do AGHU (não "lixo"), mas, para
    o SAA — cujo único interesse é "que sala está alocada nesse horário?" —
    elas representam a MESMA grade e devem aparecer só uma vez. Por isso
    listar_grades()/buscar_grade() deduplicam por (grade_id, dia_semana,
    turno), mantendo a primeira ocorrência. O arquivo de origem nunca é
    alterado: quem precisa da granularidade por linha (relatórios de
    capacidade/qualidade em /api/aghu/*) continua lendo GradeAghuCsvProvider
    diretamente, sem passar por este adapter.
"""
from __future__ import annotations

from pathlib import Path

from src.models.schemas import Grade, GradeAghu
from src.providers.implementations.grade_aghu_csv_provider import GradeAghuCsvProvider
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface


class GradeAghuDashboardProvider(GradeProviderInterface):
    """Adapta GradeAghuCsvProvider (formato real AGHU) para o contrato Grade do SAA.

    Garante a regra "grades não podem se repetir": deduplica por
    (grade_id, dia_semana, turno) — ver docstring do módulo.
    """

    def __init__(self, caminho: Path = Path("data/vw_grades.csv")) -> None:
        self._provider = GradeAghuCsvProvider(caminho=caminho)

    def listar_grades(self) -> list[Grade]:
        vistas: set[tuple[str, str, str]] = set()
        grades: list[Grade] = []
        for g in self._provider.listar_grades():
            chave = (g.grade_id, g.dia_semana, g.turno)
            if chave in vistas:
                continue
            vistas.add(chave)
            grades.append(self._adaptar(g))
        return grades

    def buscar_grade(self, grade_id: str) -> Grade | None:
        return next((g for g in self.listar_grades() if g.id == grade_id), None)

    def relatorio_duplicadas(self) -> tuple[int, int]:
        """Retorna (total_linhas_brutas, total_grades_unicas), usado pelo
        endpoint de verificação/normalização de grades duplicadas
        (POST /api/grades/remover-duplicadas). Não modifica nada em disco —
        a deduplicação já é automática em listar_grades()."""
        brutas = self._provider.listar_grades()
        unicas = {(g.grade_id, g.dia_semana, g.turno) for g in brutas}
        return len(brutas), len(unicas)

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
