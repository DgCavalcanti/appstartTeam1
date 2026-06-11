"""
test_alocacao_controller.py — Testes unitários do AlocacaoController

Usa um provider fake (in-memory) para isolar o controller do CSV e do banco.
Cobre:
  - Fluxo feliz (grades e salas válidas)
  - Provider sem dados / arquivo ausente
  - Conversão de ResultadoMotor para Alocacao
  - Persistência chamada corretamente
"""
from __future__ import annotations

import pytest

from src.controllers.alocacao_controller import AlocacaoController
from src.models.schemas import Alocacao, Grade, Sala
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface


# ---------------------------------------------------------------------------
# Provider Fake
# ---------------------------------------------------------------------------

class FakeProvider(AlocacaoProviderInterface):
    """Provider in-memory para testes — sem CSV, sem SQLite."""

    def __init__(
        self,
        grades: list[Grade] | None = None,
        salas: list[Sala] | None = None,
        historico: list[Alocacao] | None = None,
        erro_grades: Exception | None = None,
        erro_salas: Exception | None = None,
    ):
        self._grades    = grades or []
        self._salas     = salas or []
        self._historico = historico or []
        self._erro_grades = erro_grades
        self._erro_salas  = erro_salas
        self.alocacoes_salvas: list[Alocacao] = []

    def listar_grades(self) -> list[Grade]:
        if self._erro_grades:
            raise self._erro_grades
        return self._grades

    def listar_salas(self) -> list[Sala]:
        if self._erro_salas:
            raise self._erro_salas
        return self._salas

    def listar_historico(self) -> list[Alocacao]:
        return self._historico

    def salvar_alocacoes(self, alocacoes: list[Alocacao]) -> None:
        self.alocacoes_salvas.extend(alocacoes)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def grade(id=1, esp="cardiologia", prof="Dr. A", dia="segunda", turno="manha", qtd=1):
    return Grade(id=id, especialidade=esp, profissional=prof,
                 dia_semana=dia, turno=turno, qtd_salas_necessarias=qtd)


def sala(id=10, status="disponivel", bloco="A", andar="1",
         tem_equipamento=False, acessivel=False, tem_maca=False):
    return Sala(id=id, numero=str(id), andar=andar, bloco=bloco,
                status=status, tem_equipamento=tem_equipamento,
                acessivel=acessivel, tem_maca_ginecologica=tem_maca)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

class TestAlocacaoControllerFluxoFeliz:

    def test_retorna_resultado_motor(self):
        provider = FakeProvider(grades=[grade()], salas=[sala()])
        ctrl = AlocacaoController(provider)
        resultado = ctrl.alocar_automaticamente("segunda", "manha")
        assert resultado.dia_semana == "segunda"
        assert resultado.turno == "manha"

    def test_alocacao_persistida_apos_execucao(self):
        provider = FakeProvider(grades=[grade()], salas=[sala()])
        ctrl = AlocacaoController(provider)
        ctrl.alocar_automaticamente("segunda", "manha")
        assert len(provider.alocacoes_salvas) == 1

    def test_grade_sem_sala_nao_persiste_alocacao(self):
        provider = FakeProvider(grades=[grade()], salas=[sala(status="reforma")])
        ctrl = AlocacaoController(provider)
        ctrl.alocar_automaticamente("segunda", "manha")
        # Nenhuma alocação válida → nada persiste
        assert len(provider.alocacoes_salvas) == 0

    def test_grade_multiplas_salas_persiste_n_registros(self):
        provider = FakeProvider(
            grades=[grade(qtd=2)],
            salas=[sala(id=10), sala(id=11)],
        )
        ctrl = AlocacaoController(provider)
        ctrl.alocar_automaticamente("segunda", "manha")
        assert len(provider.alocacoes_salvas) == 2

    def test_ids_das_alocacoes_persistidas_sao_unicos(self):
        provider = FakeProvider(
            grades=[grade(id=1, qtd=2)],
            salas=[sala(id=10), sala(id=11)],
        )
        ctrl = AlocacaoController(provider)
        ctrl.alocar_automaticamente("segunda", "manha")
        ids = [a.id for a in provider.alocacoes_salvas]
        assert len(ids) == len(set(ids))

    def test_alocacao_persistida_com_dia_e_turno_corretos(self):
        provider = FakeProvider(grades=[grade()], salas=[sala()])
        ctrl = AlocacaoController(provider)
        ctrl.alocar_automaticamente("segunda", "manha")
        aloc = provider.alocacoes_salvas[0]
        assert aloc.dia_semana == "segunda"
        assert aloc.turno == "manha"
        assert aloc.status == "alocado"


class TestAlocacaoControllerFalhas:

    def test_arquivo_grades_ausente_lanca_file_not_found(self):
        provider = FakeProvider(erro_grades=FileNotFoundError("grades.csv não encontrado"))
        ctrl = AlocacaoController(provider)
        with pytest.raises(FileNotFoundError):
            ctrl.alocar_automaticamente("segunda", "manha")

    def test_csv_invalido_lanca_value_error(self):
        provider = FakeProvider(erro_salas=ValueError("Coluna obrigatória ausente"))
        ctrl = AlocacaoController(provider)
        with pytest.raises(ValueError):
            ctrl.alocar_automaticamente("segunda", "manha")

    def test_sem_grades_retorna_resultado_vazio(self):
        provider = FakeProvider(grades=[], salas=[sala()])
        ctrl = AlocacaoController(provider)
        resultado = ctrl.alocar_automaticamente("segunda", "manha")
        assert resultado.alocacoes == []
        assert resultado.grades_sem_alocacao == []