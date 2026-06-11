"""
test_alocacao_engine.py — Testes unitários do Motor de Alocação Automática

Cobre:
  - Regras bloqueantes (B1–B4)
  - Regras de pontuação (P1–P7)
  - Ordenação de prioridade de grades
  - Alocação de múltiplas salas (agrupamento por bloco)
  - Motor completo (casos feliz, sem salas, parcial)
"""
import pytest
from src.models.schemas import Grade, Sala, Alocacao
from src.services.alocacao_engine import (
    sala_e_elegivel,
    calcular_score,
    alocar,
    PESO_ESPECIALIDADE_PREFERENCIAL,
    PESO_ORTOPEDIA_ANDAR_1,
    PESO_ORTOPEDIA_ANDAR_2_3,
    PESO_ORTOPEDIA_ACESSIVEL,
    PESO_MEDICO_MESMO_BLOCO,
    PESO_HISTORICO_MESMA_SALA,
    PESO_SALA_ACESSIVEL_GERAL,
)


# ---------------------------------------------------------------------------
# Fixtures base
# ---------------------------------------------------------------------------

def make_sala(**kwargs) -> Sala:
    defaults = dict(
        id=1, numero="101", andar="1", bloco="A",
        status="disponivel", tem_equipamento=False,
        acessivel=False, especialidade_preferencial=None,
        tem_maca_ginecologica=False,
    )
    defaults.update(kwargs)
    return Sala(**defaults)


def make_grade(**kwargs) -> Grade:
    defaults = dict(
        id=1, especialidade="clinica_geral", profissional="Dr. Silva",
        dia_semana="segunda", turno="manha", qtd_salas_necessarias=1,
    )
    defaults.update(kwargs)
    return Grade(**defaults)


def make_alocacao(**kwargs) -> Alocacao:
    defaults = dict(
        id=1, id_grade=1, id_sala=1,
        dia_semana="segunda", turno="manha", status="alocado",
    )
    defaults.update(kwargs)
    return Alocacao(**defaults)


# ---------------------------------------------------------------------------
# B1 — Sala em reforma/manutenção/bloqueada
# ---------------------------------------------------------------------------

class TestRegrasBloqueanteStatus:

    def test_sala_em_reforma_eliminada(self):
        sala = make_sala(status="reforma")
        grade = make_grade()
        assert not sala_e_elegivel(grade, sala, set())

    def test_sala_em_manutencao_eliminada(self):
        sala = make_sala(status="manutencao")
        grade = make_grade()
        assert not sala_e_elegivel(grade, sala, set())

    def test_sala_bloqueada_eliminada(self):
        sala = make_sala(status="bloqueada")
        grade = make_grade()
        assert not sala_e_elegivel(grade, sala, set())

    def test_sala_disponivel_aceita(self):
        sala = make_sala(status="disponivel")
        grade = make_grade()
        assert sala_e_elegivel(grade, sala, set())


# ---------------------------------------------------------------------------
# B2 — Oftalmologia exige equipamento
# ---------------------------------------------------------------------------

class TestRegraBloqueanteOftalmologia:

    def test_oftalmologia_sem_equipamento_bloqueada(self):
        sala = make_sala(tem_equipamento=False)
        grade = make_grade(especialidade="oftalmologia")
        assert not sala_e_elegivel(grade, sala, set())

    def test_oftalmologia_com_equipamento_aceita(self):
        sala = make_sala(tem_equipamento=True)
        grade = make_grade(especialidade="oftalmologia")
        assert sala_e_elegivel(grade, sala, set())

    def test_outra_especialidade_sem_equipamento_aceita(self):
        sala = make_sala(tem_equipamento=False)
        grade = make_grade(especialidade="cardiologia")
        assert sala_e_elegivel(grade, sala, set())


# ---------------------------------------------------------------------------
# B3 — Ginecologia exige maca ginecológica
# ---------------------------------------------------------------------------

class TestRegraBloqueanteGinecologia:

    def test_ginecologia_sem_maca_bloqueada(self):
        sala = make_sala(tem_maca_ginecologica=False)
        grade = make_grade(especialidade="ginecologia")
        assert not sala_e_elegivel(grade, sala, set())

    def test_ginecologia_com_maca_aceita(self):
        sala = make_sala(tem_maca_ginecologica=True)
        grade = make_grade(especialidade="ginecologia")
        assert sala_e_elegivel(grade, sala, set())


# ---------------------------------------------------------------------------
# B4 — Sala já ocupada no turno
# ---------------------------------------------------------------------------

class TestRegraBloqueanteOcupacao:

    def test_sala_ocupada_bloqueada(self):
        sala = make_sala(id=5)
        grade = make_grade()
        assert not sala_e_elegivel(grade, sala, salas_ocupadas={5})

    def test_sala_livre_aceita(self):
        sala = make_sala(id=5)
        grade = make_grade()
        assert sala_e_elegivel(grade, sala, salas_ocupadas={99})


# ---------------------------------------------------------------------------
# P1 — Especialidade preferencial
# ---------------------------------------------------------------------------

class TestPontuacaoEspecialidadePreferencial:

    def test_match_especialidade_soma_peso(self):
        sala = make_sala(especialidade_preferencial="cardiologia")
        grade = make_grade(especialidade="cardiologia")
        score = calcular_score(grade, sala, [], set())
        assert score >= PESO_ESPECIALIDADE_PREFERENCIAL

    def test_sem_match_nao_soma(self):
        sala = make_sala(especialidade_preferencial="neurologia")
        grade = make_grade(especialidade="cardiologia")
        score = calcular_score(grade, sala, [], set())
        assert score < PESO_ESPECIALIDADE_PREFERENCIAL

    def test_sem_especialidade_preferencial_nao_soma(self):
        sala = make_sala(especialidade_preferencial=None)
        grade = make_grade(especialidade="cardiologia")
        score = calcular_score(grade, sala, [], set())
        assert score < PESO_ESPECIALIDADE_PREFERENCIAL


# ---------------------------------------------------------------------------
# P2/P3/P4 — Ortopedia
# ---------------------------------------------------------------------------

class TestPontuacaoOrtopedia:

    def test_andar_1_soma_peso_maximo(self):
        sala = make_sala(andar="1", acessivel=False)
        grade = make_grade(especialidade="ortopedia")
        score = calcular_score(grade, sala, [], set())
        assert score >= PESO_ORTOPEDIA_ANDAR_1

    def test_andar_2_soma_peso_medio(self):
        sala = make_sala(andar="2", acessivel=False)
        grade = make_grade(especialidade="ortopedia")
        score = calcular_score(grade, sala, [], set())
        assert PESO_ORTOPEDIA_ANDAR_2_3 <= score < PESO_ORTOPEDIA_ANDAR_1

    def test_andar_1_e_acessivel_soma_ambos_pesos(self):
        sala = make_sala(andar="1", acessivel=True)
        grade = make_grade(especialidade="ortopedia")
        score = calcular_score(grade, sala, [], set())
        esperado = PESO_ORTOPEDIA_ANDAR_1 + PESO_ORTOPEDIA_ACESSIVEL + PESO_SALA_ACESSIVEL_GERAL
        assert score == esperado

    def test_outra_especialidade_nao_recebe_bonus_ortopedia(self):
        sala = make_sala(andar="1", acessivel=True)
        grade = make_grade(especialidade="cardiologia")
        score = calcular_score(grade, sala, [], set())
        # Não deve incluir pesos exclusivos de ortopedia
        assert score < PESO_ORTOPEDIA_ANDAR_1


# ---------------------------------------------------------------------------
# P5 — Médico já tem sala no mesmo bloco
# ---------------------------------------------------------------------------

class TestPontuacaoMedicoMesmoBloco:

    def test_sala_mesmo_bloco_soma_peso(self):
        sala_nova = make_sala(id=2, bloco="B")
        sala_existente = make_sala(id=1, bloco="B")
        grade = make_grade()
        score = calcular_score(grade, sala_nova, [sala_existente], set())
        assert score >= PESO_MEDICO_MESMO_BLOCO

    def test_sala_bloco_diferente_nao_soma(self):
        sala_nova = make_sala(id=2, bloco="C")
        sala_existente = make_sala(id=1, bloco="B")
        grade = make_grade()
        score = calcular_score(grade, sala_nova, [sala_existente], set())
        assert score < PESO_MEDICO_MESMO_BLOCO


# ---------------------------------------------------------------------------
# P6 — Histórico de uso da sala pelo médico
# ---------------------------------------------------------------------------

class TestPontuacaoHistorico:

    def test_sala_no_historico_soma_peso(self):
        sala = make_sala(id=7)
        grade = make_grade()
        score = calcular_score(grade, sala, [], {7})
        assert score >= PESO_HISTORICO_MESMA_SALA

    def test_sala_fora_do_historico_nao_soma(self):
        sala = make_sala(id=7)
        grade = make_grade()
        score = calcular_score(grade, sala, [], {99})
        assert score < PESO_HISTORICO_MESMA_SALA


# ---------------------------------------------------------------------------
# P7 — Sala acessível (bônus geral)
# ---------------------------------------------------------------------------

class TestPontuacaoAcessibilidade:

    def test_sala_acessivel_soma_bonus(self):
        sala_acessivel     = make_sala(acessivel=True)
        sala_nao_acessivel = make_sala(acessivel=False)
        grade = make_grade()
        score_ac  = calcular_score(grade, sala_acessivel, [], set())
        score_nac = calcular_score(grade, sala_nao_acessivel, [], set())
        assert score_ac - score_nac == PESO_SALA_ACESSIVEL_GERAL


# ---------------------------------------------------------------------------
# Motor completo — casos de integração
# ---------------------------------------------------------------------------

class TestMotorCompleto:

    def _grades_simples(self):
        return [
            make_grade(id=1, especialidade="cardiologia", profissional="Dr. A",
                       dia_semana="segunda", turno="manha", qtd_salas_necessarias=1),
        ]

    def _salas_simples(self):
        return [
            make_sala(id=10, numero="101", bloco="A", andar="1", status="disponivel"),
            make_sala(id=11, numero="102", bloco="A", andar="2", status="disponivel"),
        ]

    def test_caso_feliz_aloca_uma_sala(self):
        resultado = alocar("segunda", "manha", self._grades_simples(), self._salas_simples(), [])
        assert len(resultado.alocacoes) == 1
        assert resultado.alocacoes[0].alocado is True
        assert len(resultado.alocacoes[0].salas_alocadas) == 1

    def test_sem_salas_disponíveis_registra_sem_alocacao(self):
        salas_bloqueadas = [make_sala(id=10, status="reforma")]
        resultado = alocar("segunda", "manha", self._grades_simples(), salas_bloqueadas, [])
        assert resultado.alocacoes[0].alocado is False
        assert 1 in resultado.grades_sem_alocacao

    def test_oftalmologia_processada_antes_de_clinica_geral(self):
        grades = [
            make_grade(id=1, especialidade="clinica_geral", profissional="Dr. A",
                       dia_semana="segunda", turno="manha"),
            make_grade(id=2, especialidade="oftalmologia", profissional="Dr. B",
                       dia_semana="segunda", turno="manha"),
        ]
        salas = [
            make_sala(id=10, status="disponivel", tem_equipamento=True),
        ]
        resultado = alocar("segunda", "manha", grades, salas, [])
        # Sala com equipamento deve ir para oftalmologia
        aloc_oftalmo = next(a for a in resultado.alocacoes if a.especialidade == "oftalmologia")
        assert aloc_oftalmo.alocado is True
        assert 10 in aloc_oftalmo.salas_alocadas

    def test_duas_grades_nao_compartilham_sala(self):
        grades = [
            make_grade(id=1, especialidade="cardiologia", profissional="Dr. A",
                       dia_semana="segunda", turno="manha"),
            make_grade(id=2, especialidade="neurologia", profissional="Dr. B",
                       dia_semana="segunda", turno="manha"),
        ]
        salas = [
            make_sala(id=10, status="disponivel"),
            make_sala(id=11, status="disponivel"),
        ]
        resultado = alocar("segunda", "manha", grades, salas, [])
        todas_salas = [sid for a in resultado.alocacoes for sid in a.salas_alocadas]
        # Sem duplicatas — cada sala usada no máximo uma vez
        assert len(todas_salas) == len(set(todas_salas))

    def test_grade_multiplas_salas_mesmo_bloco(self):
        grade = make_grade(id=1, especialidade="cardiologia", profissional="Dr. A",
                           dia_semana="segunda", turno="manha", qtd_salas_necessarias=2)
        salas = [
            make_sala(id=10, bloco="A", status="disponivel"),
            make_sala(id=11, bloco="A", status="disponivel"),  # mesmo bloco
            make_sala(id=12, bloco="B", status="disponivel"),  # bloco diferente
        ]
        resultado = alocar("segunda", "manha", [grade], salas, [])
        alocacao = resultado.alocacoes[0]
        assert alocacao.alocado is True
        assert len(alocacao.salas_alocadas) == 2
        # As duas salas devem ser do bloco A (mesmo bloco)
        ids_escolhidos = set(alocacao.salas_alocadas)
        assert ids_escolhidos == {10, 11}

    def test_historico_influencia_escolha(self):
        grade = make_grade(id=1, especialidade="cardiologia", profissional="Dr. A",
                           dia_semana="segunda", turno="manha")
        salas = [
            make_sala(id=20, status="disponivel"),  # sala do histórico
            make_sala(id=21, status="disponivel"),
        ]
        historico = [make_alocacao(id=1, id_grade=1, id_sala=20,
                                   dia_semana="terca", turno="manha")]
        resultado = alocar("segunda", "manha", [grade], salas, historico)
        # Sala 20 deve ser preferida por estar no histórico
        assert resultado.alocacoes[0].salas_alocadas[0] == 20

    def test_grades_de_outro_dia_ignoradas(self):
        grades = [
            make_grade(id=1, dia_semana="terca", turno="manha"),
        ]
        resultado = alocar("segunda", "manha", grades, self._salas_simples(), [])
        assert len(resultado.alocacoes) == 0

    def test_resultado_registra_dia_e_turno(self):
        resultado = alocar("quarta", "tarde", [], [], [])
        assert resultado.dia_semana == "quarta"
        assert resultado.turno == "tarde"
