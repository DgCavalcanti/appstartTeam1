"""
test_alocacao_router.py — Testes do Router de Alocação

Usa TestClient do FastAPI com dependency_overrides para isolar o provider.
Cobre:
  - Parâmetros válidos → 200
  - dia_semana inválido → 422
  - turno inválido → 422
  - Arquivo ausente no provider → 424
  - CSV malformado → 422
  - GET /api/alocacoes com filtros
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.models.schemas import Alocacao, Grade, Sala
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface
from src.routers.alocacao import get_provider, router


# ---------------------------------------------------------------------------
# App de teste e provider fake
# ---------------------------------------------------------------------------

app = FastAPI()
app.include_router(router)


class FakeProvider(AlocacaoProviderInterface):
    def __init__(self, grades=None, salas=None, historico=None,
                 erro_grades=None, erro_salas=None):
        self._grades    = grades or []
        self._salas     = salas or []
        self._historico = historico or []
        self._erro_grades = erro_grades
        self._erro_salas  = erro_salas
        self.alocacoes_salvas: list[Alocacao] = []

    def listar_grades(self):
        if self._erro_grades:
            raise self._erro_grades
        return self._grades

    def listar_salas(self):
        if self._erro_salas:
            raise self._erro_salas
        return self._salas

    def listar_historico(self):
        return self._historico

    def salvar_alocacoes(self, alocacoes):
        self.alocacoes_salvas.extend(alocacoes)


def make_client(provider: AlocacaoProviderInterface) -> TestClient:
    app.dependency_overrides[get_provider] = lambda: provider
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /api/alocacoes/automatica
# ---------------------------------------------------------------------------

class TestPostAlocarAutomaticamente:

    def test_parametros_validos_retorna_200(self):
        provider = FakeProvider(
            grades=[Grade(id=1, especialidade="cardiologia", profissional="Dr. A",
                          dia_semana="segunda", turno="manha", qtd_salas_necessarias=1)],
            salas=[Sala(id=10, numero="101", andar="1", bloco="A",
                        status="disponivel", tem_equipamento=False,
                        acessivel=False, tem_maca_ginecologica=False)],
        )
        client = make_client(provider)
        resp = client.post("/api/alocacoes/automatica?dia_semana=segunda&turno=manha")
        assert resp.status_code == 200

    def test_resposta_contem_campos_esperados(self):
        provider = FakeProvider()
        client = make_client(provider)
        resp = client.post("/api/alocacoes/automatica?dia_semana=segunda&turno=manha")
        data = resp.json()
        assert "dia_semana" in data
        assert "turno" in data
        assert "alocacoes" in data
        assert "grades_sem_alocacao" in data

    def test_dia_invalido_retorna_422(self):
        client = make_client(FakeProvider())
        resp = client.post("/api/alocacoes/automatica?dia_semana=domingo&turno=manha")
        assert resp.status_code == 422

    def test_turno_invalido_retorna_422(self):
        client = make_client(FakeProvider())
        resp = client.post("/api/alocacoes/automatica?dia_semana=segunda&turno=noite")
        assert resp.status_code == 422

    def test_arquivo_ausente_retorna_424(self):
        provider = FakeProvider(erro_grades=FileNotFoundError("grades.csv não encontrado"))
        client = make_client(provider)
        resp = client.post("/api/alocacoes/automatica?dia_semana=segunda&turno=manha")
        assert resp.status_code == 424

    def test_csv_malformado_retorna_422(self):
        provider = FakeProvider(erro_salas=ValueError("Coluna obrigatória ausente"))
        client = make_client(provider)
        resp = client.post("/api/alocacoes/automatica?dia_semana=segunda&turno=manha")
        assert resp.status_code == 422

    def test_parametros_ausentes_retorna_422(self):
        client = make_client(FakeProvider())
        resp = client.post("/api/alocacoes/automatica")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/alocacoes
# ---------------------------------------------------------------------------

class TestGetListarAlocacoes:

    def _historico(self):
        return [
            Alocacao(id=1, id_grade=1, id_sala=10,
                     dia_semana="segunda", turno="manha", status="alocado"),
            Alocacao(id=2, id_grade=2, id_sala=11,
                     dia_semana="terca", turno="tarde", status="alocado"),
        ]

    def test_sem_filtros_retorna_todos(self):
        client = make_client(FakeProvider(historico=self._historico()))
        resp = client.get("/api/alocacoes")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filtro_dia_semana(self):
        client = make_client(FakeProvider(historico=self._historico()))
        resp = client.get("/api/alocacoes?dia_semana=segunda")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["dia_semana"] == "segunda"

    def test_filtro_turno(self):
        client = make_client(FakeProvider(historico=self._historico()))
        resp = client.get("/api/alocacoes?turno=tarde")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["turno"] == "tarde"

    def test_filtro_combinado(self):
        client = make_client(FakeProvider(historico=self._historico()))
        resp = client.get("/api/alocacoes?dia_semana=segunda&turno=manha")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filtro_sem_resultado_retorna_lista_vazia(self):
        client = make_client(FakeProvider(historico=self._historico()))
        resp = client.get("/api/alocacoes?dia_semana=sexta")
        assert resp.status_code == 200
        assert resp.json() == [] 