"""
Testes dos routers SAA.

Cobre:
  - GET /api/grades
  - GET /api/salas
  - GET /api/restricoes
  - GET /api/alocacoes
  - GET /api/dashboard/resumo
  - GET /api/dashboard/conflitos
  - POST /api/alocacoes/ajustar — caso feliz
  - POST /api/alocacoes/ajustar — exige justificativa com conflito
  - POST /api/alocacoes/ajustar — alocação inexistente → 422
  - GET /api/alocacoes/historico — registrado após ajuste
  - POST /api/alocacoes/automatica — alocação automática por dia/turno
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.models.schemas import Alocacao, Grade, Sala
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface
from src.providers.interfaces.historico_provider_interface import (
    AlocacaoSaaProviderInterface,
    HistoricoProviderInterface,
)
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface
from src.models.schemas import HistoricoAjuste

# ── Providers fake ────────────────────────────────────────────────────────────


class FakeGradeProvider(GradeProviderInterface):
    def __init__(self, grades=None):
        self._grades = grades or []

    def listar_grades(self):
        return self._grades

    def buscar_grade(self, grade_id):
        return next((g for g in self._grades if g.id == grade_id), None)


class FakeSalaProvider(SalaProviderInterface):
    def __init__(self, salas=None):
        self._salas = salas or []

    def listar_salas(self):
        return self._salas

    def buscar_sala(self, sala_id):
        return next((s for s in self._salas if s.id == sala_id), None)


class FakeRestricaoProvider(RestricaoProviderInterface):
    def __init__(self, restricoes=None):
        self._restricoes = restricoes or []

    def listar_restricoes(self):
        return self._restricoes


class FakeAlocacaoProvider(AlocacaoSaaProviderInterface):
    def __init__(self, alocacoes=None):
        self._alocacoes: list[Alocacao] = list(alocacoes or [])

    def listar_alocacoes(self):
        return list(self._alocacoes)

    def buscar_alocacao(self, alocacao_id):
        return next((a for a in self._alocacoes if a.id == alocacao_id), None)

    def atualizar_alocacao(self, alocacao: Alocacao):
        for i, a in enumerate(self._alocacoes):
            if a.id == alocacao.id:
                self._alocacoes[i] = alocacao
                return
        self._alocacoes.append(alocacao)


class FakeHistoricoProvider(HistoricoProviderInterface):
    def __init__(self):
        self._historico: list[HistoricoAjuste] = []

    def registrar(self, entrada: HistoricoAjuste):
        self._historico.insert(0, entrada)

    def listar(self):
        return list(self._historico)


# ── Dados de teste ────────────────────────────────────────────────────────────

def _grade(**kw) -> Grade:
    defaults = dict(id="G001", especialidade="Cardiologia", profissional="Dr. A",
                    dia_semana="Segunda", turno="Manhã", qtd_salas_necessarias=1)
    return Grade(**{**defaults, **kw})


def _sala(**kw) -> Sala:
    defaults = dict(id="S001", numero="101", bloco="A", andar="1",
                    status="disponivel", acessibilidade=True,
                    equipamentos=[], especialidade_preferencial=None)
    return Sala(**{**defaults, **kw})


def _aloc(**kw) -> Alocacao:
    defaults = dict(id="A001", grade_id="G001", sala_id="S001",
                    dia_semana="Segunda", turno="Manhã")
    return Alocacao(**{**defaults, **kw})


# ── Montagem do app de teste ──────────────────────────────────────────────────

from src.routers import grade as grade_router
from src.routers import sala as sala_router
from src.routers import restricao as restricao_router
from src.routers import alocacao as alocacao_router
from src.routers import dashboard as dashboard_router
from src.controllers.alocacao_controller import AlocacaoController
from src.controllers.dashboard_controller import DashboardController

app = FastAPI()
app.include_router(grade_router.router)
app.include_router(sala_router.router)
app.include_router(restricao_router.router)
app.include_router(alocacao_router.router)
app.include_router(dashboard_router.router)


def _make_alocacao_controller(
    grades=None, salas=None, restricoes=None, alocacoes=None
) -> AlocacaoController:
    return AlocacaoController(
        alocacao_provider=FakeAlocacaoProvider(alocacoes),
        grade_provider=FakeGradeProvider(grades),
        sala_provider=FakeSalaProvider(salas),
        restricao_provider=FakeRestricaoProvider(restricoes),
        historico_provider=FakeHistoricoProvider(),
    )


def _make_dashboard_controller(
    grades=None, salas=None, restricoes=None, alocacoes=None
) -> DashboardController:
    return DashboardController(
        grade_provider=FakeGradeProvider(grades),
        sala_provider=FakeSalaProvider(salas),
        restricao_provider=FakeRestricaoProvider(restricoes),
        alocacao_provider=FakeAlocacaoProvider(alocacoes),
    )


# ── GET /api/grades ───────────────────────────────────────────────────────────

class TestGetGrades:

    def test_retorna_200_lista(self):
        app.dependency_overrides[grade_router.get_grade_controller] = \
            lambda: grade_router.GradeController(FakeGradeProvider([_grade()]))
        resp = TestClient(app).get("/api/grades")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_lista_vazia_retorna_200(self):
        app.dependency_overrides[grade_router.get_grade_controller] = \
            lambda: grade_router.GradeController(FakeGradeProvider([]))
        resp = TestClient(app).get("/api/grades")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_arquivo_ausente_retorna_424(self):
        def _ctrl():
            raise FileNotFoundError("grades.csv não encontrado")

        original_listar = grade_router.GradeController.listar_grades

        def _bad_listar(self, **kw):
            raise FileNotFoundError("grades.csv não encontrado")

        grade_router.GradeController.listar_grades = _bad_listar
        try:
            resp = TestClient(app).get("/api/grades")
            assert resp.status_code == 424
        finally:
            grade_router.GradeController.listar_grades = original_listar


# ── GET /api/salas ────────────────────────────────────────────────────────────

class TestGetSalas:

    def test_retorna_lista_salas(self):
        app.dependency_overrides[sala_router.get_sala_controller] = \
            lambda: sala_router.SalaController(FakeSalaProvider([_sala()]))
        resp = TestClient(app).get("/api/salas")
        assert resp.status_code == 200
        data = resp.json()
        assert data[0]["id"] == "S001"
        assert isinstance(data[0]["equipamentos"], list)

    def test_filtro_status(self):
        salas = [_sala(id="S001", status="disponivel"), _sala(id="S002", numero="102", status="bloqueada")]
        app.dependency_overrides[sala_router.get_sala_controller] = \
            lambda: sala_router.SalaController(FakeSalaProvider(salas))
        resp = TestClient(app).get("/api/salas?status=disponivel")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── GET /api/alocacoes ────────────────────────────────────────────────────────

class TestGetAlocacoes:

    def test_retorna_lista_alocacoes(self):
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: _make_alocacao_controller(alocacoes=[_aloc()])
        resp = TestClient(app).get("/api/alocacoes")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filtro_dia_semana(self):
        alocs = [_aloc(id="A001", dia_semana="Segunda"),
                 _aloc(id="A002", dia_semana="Terça", sala_id="S002")]
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: _make_alocacao_controller(alocacoes=alocs)
        resp = TestClient(app).get("/api/alocacoes?dia_semana=segunda")
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ── GET /api/dashboard/resumo ─────────────────────────────────────────────────

class TestGetDashboardResumo:

    def test_retorna_resumo(self):
        app.dependency_overrides[dashboard_router.get_dashboard_controller] = \
            lambda: _make_dashboard_controller(
                grades=[_grade()], salas=[_sala()], alocacoes=[_aloc()]
            )
        resp = TestClient(app).get("/api/dashboard/resumo")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_salas" in data
        assert "conflitos_criticos" in data


# ── GET /api/dashboard/conflitos ──────────────────────────────────────────────

class TestGetDashboardConflitos:

    def test_sem_conflitos(self):
        app.dependency_overrides[dashboard_router.get_dashboard_controller] = \
            lambda: _make_dashboard_controller(
                grades=[_grade()], salas=[_sala()], alocacoes=[_aloc()]
            )
        resp = TestClient(app).get("/api/dashboard/conflitos")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_sala_reforma_aparece_como_conflito(self):
        sala  = _sala(status="reforma")
        grade = _grade()
        aloc  = _aloc()
        app.dependency_overrides[dashboard_router.get_dashboard_controller] = \
            lambda: _make_dashboard_controller(grades=[grade], salas=[sala], alocacoes=[aloc])
        resp = TestClient(app).get("/api/dashboard/conflitos")
        assert resp.status_code == 200
        conflitos = resp.json()
        assert any(c["tipo"] == "sala_em_reforma" for c in conflitos)


# ── POST /api/alocacoes/ajustar ───────────────────────────────────────────────

class TestPostAjustarAlocacao:

    def _controller(self, grades=None, salas=None, alocacoes=None):
        salas = salas or [_sala(), _sala(id="S002", numero="102")]
        return _make_alocacao_controller(
            grades=grades or [_grade()],
            salas=salas,
            alocacoes=alocacoes or [_aloc()],
        )

    def test_ajuste_valido_retorna_200(self):
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: self._controller()
        resp = TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "A001",
            "nova_sala_id": "S002",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["alocacao"]["sala_id"] == "S002"
        assert "historico" in data

    def test_alocacao_inexistente_retorna_422(self):
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: self._controller()
        resp = TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "XPTO",
            "nova_sala_id": "S002",
        })
        assert resp.status_code == 422

    def test_sala_nova_inexistente_retorna_422(self):
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: self._controller()
        resp = TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "A001",
            "nova_sala_id": "S999",
        })
        assert resp.status_code == 422

    def test_conflito_critico_sem_justificativa_retorna_422(self):
        sala_reforma = _sala(id="S002", numero="102", status="reforma")
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: self._controller(salas=[_sala(), sala_reforma])
        resp = TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "A001",
            "nova_sala_id": "S002",
        })
        assert resp.status_code == 422
        assert "justificativa" in resp.json()["detail"].lower()

    def test_conflito_critico_com_justificativa_retorna_200(self):
        sala_reforma = _sala(id="S002", numero="102", status="reforma")
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = \
            lambda: self._controller(salas=[_sala(), sala_reforma])
        resp = TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "A001",
            "nova_sala_id": "S002",
            "justificativa": "Única sala disponível no momento.",
        })
        assert resp.status_code == 200


# ── GET /api/alocacoes/historico ──────────────────────────────────────────────

class TestGetHistorico:

    def test_historico_registrado_apos_ajuste(self):
        controller = _make_alocacao_controller(
            grades=[_grade()],
            salas=[_sala(), _sala(id="S002", numero="102")],
            alocacoes=[_aloc()],
        )
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = lambda: controller

        # Realiza ajuste
        TestClient(app).post("/api/alocacoes/ajustar", json={
            "alocacao_id": "A001", "nova_sala_id": "S002"
        })

        # Verifica histórico
        resp = TestClient(app).get("/api/alocacoes/historico")
        assert resp.status_code == 200
        historico = resp.json()
        assert len(historico) == 1
        assert historico[0]["sala_anterior_id"] == "S001"
        assert historico[0]["sala_nova_id"] == "S002"


# ── POST /api/alocacoes/automatica ────────────────────────────────────────────

class TestAlocacaoAutomatica:

    def test_post_automatica_cria_alocacao(self):
        controller = _make_alocacao_controller(
            grades=[_grade()],
            salas=[_sala()],
            alocacoes=[],
        )
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = lambda: controller

        resp = TestClient(app).post("/api/alocacoes/automatica", json={
            "dia_semana": "Segunda",
            "turno": "Manhã",
        })

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_grades"] == 1
        assert data["total_alocadas"] == 1
        assert len(data["alocacoes_persistidas"]) == 1
        assert controller.listar_alocacoes()[0].sala_id == "S001"

    def test_post_automatica_nao_duplica_alocacao_existente(self):
        controller = _make_alocacao_controller(
            grades=[_grade()],
            salas=[_sala(), _sala(id="S002", numero="102")],
            alocacoes=[_aloc()],
        )
        app.dependency_overrides[alocacao_router.get_alocacao_controller] = lambda: controller
        client = TestClient(app)

        for _ in range(2):
            resp = client.post("/api/alocacoes/automatica", json={
                "dia_semana": "segunda",
                "turno": "manha",
            })
            assert resp.status_code == 200

        assert len(controller.listar_alocacoes()) == 1
