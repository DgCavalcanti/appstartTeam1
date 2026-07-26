"""
test_padroes.py — Padrões globais herdados pelos cenários novos.

Cobre a edição do panorama do catálogo, o CRUD das restrições padrão e a
semeadura das restrições num cenário recém-criado.
"""

from __future__ import annotations

import pytest

from src.domain.entidades import NUM_TURNOS, OBRIGATORIO, PREFERENCIAL, Clinica, indice_turno
from src.domain.importacao import GradeDemanda, GradeSlot
from src.repositories import AlocacaoRepository, CatalogoRepository, PavimentoEntrada

from tests.test_servicos import executar


async def _catalogo_semeado(sessao) -> CatalogoRepository:
    catalogo = CatalogoRepository(sessao)
    await catalogo.semear_referencia()
    await sessao.flush()
    return catalogo


# ---------------------------------------------------------------------------
# Panorama padrão
# ---------------------------------------------------------------------------


class TestPanoramaPadrao:

    def test_editar_contagem_recalcula_capacidade(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pavimentos = await catalogo.listar_pavimentos()
            alvo = next(p for p in pavimentos if p.capacidade > 0)
            antes = alvo.capacidade
            atualizado = await catalogo.editar_pavimento_padrao(
                alvo.id, {"padrao_1est": alvo.padrao_1est + 4}
            )
            return antes, atualizado.capacidade

        antes, depois = executar(rodar)
        assert depois == antes + 4

    def test_campo_desconhecido_e_recusado(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            alvo = (await catalogo.listar_pavimentos())[0]
            with pytest.raises(ValueError, match="campos desconhecidos"):
                await catalogo.editar_pavimento_padrao(alvo.id, {"capacidade": 99})

        executar(rodar)

    def test_pavimento_inexistente(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            return await catalogo.editar_pavimento_padrao(9999, {"padrao_1est": 1})

        assert executar(rodar) is None


# ---------------------------------------------------------------------------
# Restrições padrão — CRUD
# ---------------------------------------------------------------------------


class TestRestricoesPadraoCrud:

    def test_definir_e_listar(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = next(p for p in await catalogo.listar_pavimentos() if p.capacidade > 0)
            await catalogo.definir_restricao_padrao(
                "CARDIOLOGIA (AMBULATÓRIO)", pav.id, OBRIGATORIO
            )
            return await catalogo.listar_restricoes_padrao()

        restricoes = executar(rodar)
        assert len(restricoes) == 1
        assert restricoes[0].tipo == OBRIGATORIO
        assert restricoes[0].unidade_normalizada == "cardiologia (ambulatorio)"

    def test_uma_obrigatoriedade_padrao_por_clinica(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pavs = [p for p in await catalogo.listar_pavimentos() if p.capacidade > 0]
            await catalogo.definir_restricao_padrao("CARDIOLOGIA (AMBULATÓRIO)", pavs[0].id, OBRIGATORIO)
            await catalogo.definir_restricao_padrao("CARDIOLOGIA (AMBULATÓRIO)", pavs[1].id, OBRIGATORIO)
            return await catalogo.listar_restricoes_padrao()

        restricoes = executar(rodar)
        assert len(restricoes) == 1, "a segunda obrigatoriedade substitui a primeira"

    def test_preferencia_coexiste_com_obrigatoriedade(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pavs = [p for p in await catalogo.listar_pavimentos() if p.capacidade > 0]
            await catalogo.definir_restricao_padrao("PEDIATRIA (AMBULATÓRIO)", pavs[0].id, OBRIGATORIO)
            await catalogo.definir_restricao_padrao("PEDIATRIA (AMBULATÓRIO)", pavs[1].id, PREFERENCIAL)
            return sorted(r.tipo for r in await catalogo.listar_restricoes_padrao())

        assert executar(rodar) == [OBRIGATORIO, PREFERENCIAL]

    def test_tipo_invalido(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = (await catalogo.listar_pavimentos())[0]
            with pytest.raises(ValueError, match="tipo inválido"):
                await catalogo.definir_restricao_padrao("CARDIOLOGIA", pav.id, "talvez")

        executar(rodar)

    def test_pavimento_inexistente(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            with pytest.raises(ValueError, match="não existe no catálogo"):
                await catalogo.definir_restricao_padrao("CARDIOLOGIA", 9999, OBRIGATORIO)

        executar(rodar)

    def test_remover(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = next(p for p in await catalogo.listar_pavimentos() if p.capacidade > 0)
            r = await catalogo.definir_restricao_padrao("CARDIOLOGIA (AMBULATÓRIO)", pav.id, PREFERENCIAL)
            removida = await catalogo.remover_restricao_padrao(r.id)
            return removida, await catalogo.listar_restricoes_padrao()

        removida, restantes = executar(rodar)
        assert removida is True
        assert restantes == []

    def test_remover_inexistente(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            return await catalogo.remover_restricao_padrao(9999)

        assert executar(rodar) is False


# ---------------------------------------------------------------------------
# Semeadura no cenário
# ---------------------------------------------------------------------------


def _cenario_de_exemplo():
    manha = tuple(10 if t % 2 == 0 else 0 for t in range(NUM_TURNOS))
    clinicas = (
        Clinica(id=1, nome="CARDIOLOGIA", demanda=manha),
        Clinica(id=2, nome="ORTOPEDIA", demanda=manha),
    )
    slots = (GradeSlot("Dr. A", "CARDIOLOGIA", "segunda", "manha"),)
    demandas = (
        GradeDemanda("CARDIOLOGIA", "segunda", "manha", 10),
        GradeDemanda("ORTOPEDIA", "segunda", "manha", 10),
    )
    return clinicas, slots, demandas


async def _criar_cenario(sessao, catalogo):
    """Cria um cenário cujos pavimentos são cópias do catálogo (mesmo bloco/nome)."""
    clinicas, slots, demandas = _cenario_de_exemplo()
    pavimentos_cat = [p for p in await catalogo.listar_pavimentos() if p.capacidade > 0]
    entradas = tuple(
        PavimentoEntrada(
            bloco=p.bloco, nome=p.nome,
            padrao_1est=p.padrao_1est, padrao_2est=p.padrao_2est,
            esp_1est=p.esp_1est, esp_2est=p.esp_2est, fechada=p.fechada,
        )
        for p in pavimentos_cat
    )
    repo = AlocacaoRepository(sessao)
    cenario = await repo.criar(
        nome="C", clinicas=clinicas, slots=slots, demandas=demandas, pavimentos=entradas
    )
    await sessao.flush()
    return await repo.obter(cenario.id)


class TestSemeadura:

    def test_restricao_padrao_e_herdada(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = next(p for p in await catalogo.listar_pavimentos() if p.capacidade > 0)
            await catalogo.definir_restricao_padrao("CARDIOLOGIA", pav.id, OBRIGATORIO)

            cenario = await _criar_cenario(sessao, catalogo)
            criadas = await catalogo.semear_restricoes_no_cenario(cenario)
            return criadas, cenario.restricoes

        criadas, restricoes = executar(rodar)
        assert criadas == 1
        assert restricoes[0].tipo == OBRIGATORIO

    def test_pula_clinica_ausente_no_cenario(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = next(p for p in await catalogo.listar_pavimentos() if p.capacidade > 0)
            # DERMATOLOGIA não está no cenário de exemplo (só CARDIO e ORTO).
            await catalogo.definir_restricao_padrao("DERMATOLOGIA (AMBULATÓRIO)", pav.id, OBRIGATORIO)

            cenario = await _criar_cenario(sessao, catalogo)
            return await catalogo.semear_restricoes_no_cenario(cenario)

        assert executar(rodar) == 0

    def test_casa_pavimento_por_bloco_e_nome(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            pav = next(p for p in await catalogo.listar_pavimentos() if p.capacidade > 0)
            await catalogo.definir_restricao_padrao("ORTOPEDIA", pav.id, PREFERENCIAL)

            cenario = await _criar_cenario(sessao, catalogo)
            await catalogo.semear_restricoes_no_cenario(cenario)

            # A restrição do cenário aponta para o pavimento do cenário com o
            # mesmo bloco/nome do pavimento do catálogo escolhido.
            destino = next(
                p for p in cenario.pavimentos
                if p.id == cenario.restricoes[0].pavimento_id
            )
            return destino.bloco, destino.nome, pav.bloco, pav.nome

        b_cenario, n_cenario, b_cat, n_cat = executar(rodar)
        assert (b_cenario, n_cenario) == (b_cat, n_cat)

    def test_sem_padrao_nao_semeia_nada(self):
        async def rodar(sessao):
            catalogo = await _catalogo_semeado(sessao)
            cenario = await _criar_cenario(sessao, catalogo)
            return await catalogo.semear_restricoes_no_cenario(cenario)

        assert executar(rodar) == 0
