"""Testes do serviço de conflitos do SAA — cobre as 10 regras MVP."""
from __future__ import annotations

import pytest
from src.models.schemas import Alocacao, Grade, Restricao, Sala
from src.services.conflito_service import calcular_conflitos


# ── Helpers de fixture ────────────────────────────────────────────────────────

def _sala(
    id="S001", numero="101", bloco="A", andar="1",
    status="disponivel", acessibilidade=True,
    equipamentos=None, especialidade_preferencial=None,
) -> Sala:
    return Sala(
        id=id, numero=numero, bloco=bloco, andar=andar,
        status=status, acessibilidade=acessibilidade,
        equipamentos=equipamentos or [],
        especialidade_preferencial=especialidade_preferencial,
    )


def _grade(
    id="G001", especialidade="Cardiologia", profissional="Dr. X",
    dia_semana="Segunda", turno="Manhã", qtd_salas_necessarias=1,
) -> Grade:
    return Grade(
        id=id, especialidade=especialidade, profissional=profissional,
        dia_semana=dia_semana, turno=turno,
        qtd_salas_necessarias=qtd_salas_necessarias,
    )


def _aloc(id="A001", grade_id="G001", sala_id="S001", dia_semana="Segunda", turno="Manhã") -> Alocacao:
    return Alocacao(id=id, grade_id=grade_id, sala_id=sala_id, dia_semana=dia_semana, turno=turno)


def _restricao(id="R001", sala_id="S001", tipo="equipamento_obrigatorio", valor="ECG") -> Restricao:
    return Restricao(id=id, sala_id=sala_id, tipo=tipo, valor=valor)


# ── C01: Sala em reforma ──────────────────────────────────────────────────────

class TestC01SalaEmReforma:

    def test_sala_reforma_gera_conflito_critico(self):
        sala = _sala(status="reforma")
        aloc = _aloc()
        conflitos = calcular_conflitos([_grade()], [sala], [], [aloc])
        assert any(c.tipo == "sala_em_reforma" and c.gravidade == "critico" for c in conflitos)

    def test_sala_disponivel_nao_gera_conflito_reforma(self):
        sala = _sala(status="disponivel")
        aloc = _aloc()
        conflitos = calcular_conflitos([_grade()], [sala], [], [aloc])
        assert not any(c.tipo == "sala_em_reforma" for c in conflitos)


# ── C02: Sala em manutenção ───────────────────────────────────────────────────

class TestC02SalaEmManutencao:

    def test_sala_manutencao_gera_conflito_critico(self):
        sala = _sala(status="manutencao")
        aloc = _aloc()
        conflitos = calcular_conflitos([_grade()], [sala], [], [aloc])
        assert any(c.tipo == "sala_em_manutencao" and c.gravidade == "critico" for c in conflitos)


# ── C03: Sala bloqueada ───────────────────────────────────────────────────────

class TestC03SalaBloqueada:

    def test_sala_bloqueada_gera_conflito_critico(self):
        sala = _sala(status="bloqueada")
        aloc = _aloc()
        conflitos = calcular_conflitos([_grade()], [sala], [], [aloc])
        assert any(c.tipo == "sala_bloqueada" and c.gravidade == "critico" for c in conflitos)


# ── C04: Sala inexistente ─────────────────────────────────────────────────────

class TestC04SalaInexistente:

    def test_sala_inexistente_gera_conflito_critico(self):
        aloc = _aloc(sala_id="S999")
        conflitos = calcular_conflitos([_grade()], [], [], [aloc])
        assert any(c.tipo == "sala_inexistente" and c.gravidade == "critico" for c in conflitos)


# ── C05: Grade inexistente ────────────────────────────────────────────────────

class TestC05GradeInexistente:

    def test_grade_inexistente_gera_conflito_critico(self):
        aloc = _aloc(grade_id="G999")
        conflitos = calcular_conflitos([], [_sala()], [], [aloc])
        assert any(c.tipo == "grade_inexistente" and c.gravidade == "critico" for c in conflitos)


# ── C06: Dupla alocação ───────────────────────────────────────────────────────

class TestC06DuplaAlocacao:

    def test_mesma_sala_mesmo_dia_turno_gera_conflito_critico(self):
        sala = _sala()
        g1 = _grade(id="G001")
        g2 = _grade(id="G002")
        a1 = _aloc(id="A001", grade_id="G001")
        a2 = _aloc(id="A002", grade_id="G002")
        conflitos = calcular_conflitos([g1, g2], [sala], [], [a1, a2])
        assert any(c.tipo == "dupla_alocacao" and c.gravidade == "critico" for c in conflitos)

    def test_sala_diferente_nao_gera_dupla_alocacao(self):
        s1 = _sala(id="S001")
        s2 = _sala(id="S002", numero="102")
        g1 = _grade(id="G001")
        g2 = _grade(id="G002")
        a1 = _aloc(id="A001", grade_id="G001", sala_id="S001")
        a2 = _aloc(id="A002", grade_id="G002", sala_id="S002")
        conflitos = calcular_conflitos([g1, g2], [s1, s2], [], [a1, a2])
        assert not any(c.tipo == "dupla_alocacao" for c in conflitos)


# ── C07: Grade sem sala ───────────────────────────────────────────────────────

class TestC07GradeSemSala:

    def test_grade_sem_alocacao_gera_conflito_critico(self):
        grade = _grade()
        conflitos = calcular_conflitos([grade], [], [], [])
        assert any(c.tipo == "grade_sem_sala" and c.gravidade == "critico" for c in conflitos)

    def test_grade_com_alocacao_nao_gera_grade_sem_sala(self):
        grade = _grade()
        sala  = _sala()
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert not any(c.tipo == "grade_sem_sala" for c in conflitos)


# ── C08: Especialidade incompatível ──────────────────────────────────────────

class TestC08EspecialidadeIncompativel:

    def test_sala_preferencial_diferente_gera_operacional(self):
        sala  = _sala(especialidade_preferencial="Ginecologia")
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert any(c.tipo == "especialidade_incompativel" and c.gravidade == "operacional" for c in conflitos)

    def test_sala_geral_nao_gera_incompatibilidade(self):
        sala  = _sala(especialidade_preferencial="Geral")
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert not any(c.tipo == "especialidade_incompativel" for c in conflitos)

    def test_sala_sem_preferencia_nao_gera_incompatibilidade(self):
        sala  = _sala(especialidade_preferencial=None)
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert not any(c.tipo == "especialidade_incompativel" for c in conflitos)


# ── C09: Equipamento obrigatório ausente ─────────────────────────────────────

class TestC09EquipamentoAusente:

    def test_equipamento_ausente_gera_operacional(self):
        sala      = _sala(equipamentos=[])
        grade     = _grade()
        aloc      = _aloc()
        restricao = _restricao(sala_id="S001", valor="ECG")
        conflitos = calcular_conflitos([grade], [sala], [restricao], [aloc])
        assert any(c.tipo == "equipamento_ausente" and c.gravidade == "operacional" for c in conflitos)

    def test_equipamento_presente_nao_gera_conflito(self):
        sala      = _sala(equipamentos=["ECG"])
        grade     = _grade()
        aloc      = _aloc()
        restricao = _restricao(sala_id="S001", valor="ECG")
        conflitos = calcular_conflitos([grade], [sala], [restricao], [aloc])
        assert not any(c.tipo == "equipamento_ausente" for c in conflitos)


# ── C10: Ortopedia acessibilidade ─────────────────────────────────────────────

class TestC10OrtopediaAcessibilidade:

    def test_ortopedia_sala_inacessivel_gera_operacional(self):
        sala  = _sala(acessibilidade=False, andar="1")
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert any(c.tipo == "ortopedia_acessibilidade" and c.gravidade == "operacional" for c in conflitos)

    def test_ortopedia_andar_alto_gera_operacional(self):
        sala  = _sala(acessibilidade=True, andar="3")
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert any(c.tipo == "ortopedia_acessibilidade" for c in conflitos)

    def test_ortopedia_sala_acessivel_andar_1_sem_conflito(self):
        sala  = _sala(acessibilidade=True, andar="1")
        grade = _grade(especialidade="Ortopedia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert not any(c.tipo == "ortopedia_acessibilidade" for c in conflitos)

    def test_outra_especialidade_nao_gera_c10(self):
        sala  = _sala(acessibilidade=False, andar="1")
        grade = _grade(especialidade="Cardiologia")
        aloc  = _aloc()
        conflitos = calcular_conflitos([grade], [sala], [], [aloc])
        assert not any(c.tipo == "ortopedia_acessibilidade" for c in conflitos)


# ── Caso geral sem conflitos ──────────────────────────────────────────────────

class TestSemConflitos:

    def test_dados_validos_sem_conflitos(self):
        sala  = _sala(acessibilidade=True, andar="1", especialidade_preferencial="Cardiologia", equipamentos=["ECG"])
        grade = _grade(especialidade="Cardiologia")
        aloc  = _aloc()
        restricao = _restricao(sala_id="S001", valor="ECG")
        conflitos = calcular_conflitos([grade], [sala], [restricao], [aloc])
        assert conflitos == []
