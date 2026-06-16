"""Testes dos serviços de capacidade e qualidade de dados."""
from __future__ import annotations

import pytest
from src.models.schemas import GradeAghu
from src.services.capacidade_service import (
    calcular_resumo,
    resumo_por_especialidade,
    resumo_por_dia_turno,
)
from src.services.qualidade_dados_service import analisar_qualidade


def _grade(**kw) -> GradeAghu:
    defaults = dict(
        grade_id="G001",
        profissional="DR. SILVA",
        unidade_funcional="AMB",
        condicao_atendimento="NORMAL",
        especialidade="CARDIOLOGIA",
        situacao_grade="ATIVO",
        dia_semana="SEGUNDA",
        hora_inicio="08:00",
        turno="MANHÃ",
        situacao_horario="ATIVO",
        quantidade_vagas=10,
        qtd_salas_necessarias=1,
    )
    return GradeAghu(**{**defaults, **kw})


def _linha(**kw) -> dict:
    defaults = {
        "Grade": "G001",
        "Especialidade": "CARDIOLOGIA",
        "Profissional": "DR. SILVA",
        "Unidade_Funcional": "AMB",
        "Dia_da_Semana": "SEGUNDA",
        "Turno": "MANHÃ",
        "Situacao_Consulta": "AGENDADO",
        "Consulta_Excedente": "N",
        "Data_Hora_Consulta": "15/01/2026 08:00:00",
    }
    return {**defaults, **kw}


class TestCalcularResumo:

    def test_contagem_basica(self):
        grades = [_grade()]
        linhas = [_linha()]
        r = calcular_resumo(grades, linhas)
        assert r.total_grades == 1
        assert r.total_consultas == 1
        assert r.consultas_marcadas == 1
        assert r.vagas_livres == 0

    def test_excedentes_contados_separadamente(self):
        """Excedentes são identificados pela flag, independentemente da situação."""
        linhas = [
            _linha(Consulta_Excedente="S", Situacao_Consulta="AGENDADO"),
            _linha(Consulta_Excedente="N", Situacao_Consulta="AGENDADO"),
        ]
        r = calcular_resumo([_grade()], linhas)
        assert r.consultas_excedentes == 1
        assert r.consultas_marcadas == 2  # ambas marcadas

    def test_taxa_ocupacao_calculada(self):
        linhas = [
            _linha(Situacao_Consulta="AGENDADO"),  # marcada
            _linha(Situacao_Consulta="LIVRE"),      # livre
        ]
        r = calcular_resumo([_grade()], linhas)
        assert r.taxa_ocupacao == pytest.approx(0.5)

    def test_taxa_excedente_calculada(self):
        linhas = [
            _linha(Consulta_Excedente="S"),
            _linha(Consulta_Excedente="N"),
            _linha(Consulta_Excedente="N"),
            _linha(Consulta_Excedente="N"),
        ]
        r = calcular_resumo([_grade()], linhas)
        assert r.taxa_excedente == pytest.approx(0.25)

    def test_sem_consultas_nao_divide_por_zero(self):
        r = calcular_resumo([_grade()], [])
        assert r.taxa_ocupacao == 0.0
        assert r.taxa_excedente == 0.0


class TestResumoPorEspecialidade:

    def test_agrupamento_por_especialidade(self):
        linhas = [
            _linha(Especialidade="CARDIOLOGIA"),
            _linha(Especialidade="ORTOPEDIA"),
            _linha(Especialidade="CARDIOLOGIA"),
        ]
        resultado = resumo_por_especialidade(linhas)
        esp_map = {r.especialidade: r for r in resultado}
        assert esp_map["CARDIOLOGIA"].total_consultas == 2
        assert esp_map["ORTOPEDIA"].total_consultas == 1

    def test_excedentes_por_especialidade(self):
        linhas = [
            _linha(Especialidade="CARDIOLOGIA", Consulta_Excedente="S"),
            _linha(Especialidade="CARDIOLOGIA", Consulta_Excedente="N"),
        ]
        resultado = resumo_por_especialidade(linhas)
        cardio = next(r for r in resultado if r.especialidade == "CARDIOLOGIA")
        assert cardio.excedentes == 1


class TestResumoPorDiaTurno:

    def test_agrupamento_dia_turno(self):
        linhas = [
            _linha(Dia_da_Semana="SEGUNDA", Turno="MANHÃ"),
            _linha(Dia_da_Semana="SEGUNDA", Turno="TARDE"),
            _linha(Dia_da_Semana="SEGUNDA", Turno="MANHÃ"),
        ]
        resultado = resumo_por_dia_turno(linhas)
        manha = next(r for r in resultado if r.dia_semana == "SEGUNDA" and r.turno == "MANHÃ")
        tarde = next(r for r in resultado if r.dia_semana == "SEGUNDA" and r.turno == "TARDE")
        assert manha.consultas_marcadas == 2
        assert tarde.consultas_marcadas == 1


class TestQualidadeDados:

    def test_sem_problemas(self):
        grades = [_grade()]
        linhas = [_linha()]
        qd = analisar_qualidade(grades, linhas)
        assert qd.total_problemas == 0
        assert qd.criticos == 0

    def test_detecta_grade_sem_dia(self):
        grades = [_grade(dia_semana="")]
        qd = analisar_qualidade(grades, [])
        cats = [p.categoria for p in qd.problemas]
        assert "Grades" in cats

    def test_detecta_consulta_sem_data(self):
        grades = [_grade()]
        linhas = [_linha(Data_Hora_Consulta="")]
        qd = analisar_qualidade(grades, linhas)
        criticos = [p for p in qd.problemas if p.gravidade == "critico"]
        assert len(criticos) >= 1

    def test_detecta_consulta_sem_grade_associada(self):
        grades = [_grade(grade_id="G001")]
        linhas = [_linha(Grade="G999")]  # grade inexistente
        qd = analisar_qualidade(grades, linhas)
        assert qd.total_problemas >= 1
