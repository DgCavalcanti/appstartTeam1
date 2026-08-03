"""
test_visualizacao.py — O painel consolidado, somente leitura.

Reaproveita a montagem de cenário de test_servicos e verifica os três recortes
do painel, com atenção à conversão de estações para salas físicas (seção 14).
"""

from __future__ import annotations

import pytest

from src.domain.entidades import OBRIGATORIO, indice_turno
from src.services import RestricoesService, VisualizacaoService

from tests.test_servicos import demanda_em, executar, montar_cenario


def montar_visualizacao(com_resultado: bool = True):
    async def rodar(sessao):
        cenario = await montar_cenario(sessao, com_resultado=com_resultado)
        return VisualizacaoService(sessao).montar(cenario)

    return executar(rodar)


class TestDisponibilidade:

    def test_cenario_sem_alocacao_nao_tem_painel(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=False)
            servico = VisualizacaoService(sessao)
            return servico.disponivel(cenario)

        assert executar(rodar) is False

    def test_montar_sem_alocacao_levanta_erro(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=False)
            with pytest.raises(ValueError, match="não foi alocado"):
                VisualizacaoService(sessao).montar(cenario)

        executar(rodar)

    def test_disponivel_apos_alocar(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            return VisualizacaoService(sessao).disponivel(cenario)

        assert executar(rodar) is True


class TestResumo:

    def test_indicadores_gerais(self):
        painel = montar_visualizacao()
        r = painel["resumo"]

        # As três clínicas (10 + 8 + 6) cabem nos dois pavimentos.
        assert r["total_alocado"] == 24
        assert r["total_nao_alocado"] == 0
        assert r["clinicas_alocadas"] == 3
        assert r["clinicas_com_sobra"] == 0
        assert 0 <= r["ocupacao_media_pct"] <= 100

    def test_conta_pavimentos_usados(self):
        painel = montar_visualizacao()
        r = painel["resumo"]
        assert r["pavimentos_totais"] == 2
        assert 1 <= r["pavimentos_usados"] <= 2

    def test_sobra_aparece_no_resumo(self):
        # Força as três clínicas no pavimento de 12 estações.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            restricoes = RestricoesService(sessao)
            for unidade in cenario.unidades:
                await restricoes.definir(
                    cenario, unidade.id, cenario.pavimentos[1].id, OBRIGATORIO
                )
            from src.services import AlocacaoService

            await AlocacaoService(sessao).executar(cenario)
            return VisualizacaoService(sessao).montar(cenario)

        painel = executar(rodar)
        assert painel["resumo"]["total_nao_alocado"] == 12
        assert painel["resumo"]["clinicas_com_sobra"] >= 1


class TestPorPavimento:

    def test_ocupacao_e_salas_por_pavimento(self):
        painel = montar_visualizacao()
        pavimentos = painel["por_pavimento"]

        assert len(pavimentos) == 2
        for p in pavimentos:
            assert len(p["ocupacao"]) == 10
            assert len(p["salas_por_turno"]) == 10
            # Nunca mais salas em uso do que o pavimento tem.
            assert p["salas_no_pico"] <= p["salas_abertas"]
            assert 0 <= p["ocupacao_pico_pct"] <= 100

    def test_salas_em_uso_convertem_estacoes(self):
        # Pavimento A tem 10 salas de 2 estações (20 estações). No pico,
        # segunda-manhã, uma clínica de 10 grades ocupa 5 salas.
        painel = montar_visualizacao()
        pico = indice_turno("segunda", "manha")
        a = next(p for p in painel["por_pavimento"] if "Bloco A" in p["nome"])

        if a["ocupacao"][pico] == 10:
            assert a["salas_por_turno"][pico] == 5

    def test_clinicas_listadas_por_pavimento(self):
        painel = montar_visualizacao()
        todas = {
            c["nome"]
            for p in painel["por_pavimento"]
            for c in p["clinicas"]
        }
        assert todas == {"CARDIOLOGIA", "ORTOPEDIA", "PEDIATRIA"}
        # Cada clínica traz sua própria linha de 10 turnos (a faixa da tela).
        for p in painel["por_pavimento"]:
            for c in p["clinicas"]:
                assert len(c["alocado"]) == 10
                assert len(c["nao_alocado"]) == 10

    def test_sem_sobra_nao_ha_demanda_nao_alocada_nem_alerta(self):
        # Cenário base: as três clínicas cabem inteiras — nenhum pavimento
        # deveria mostrar demanda não alocada nem alerta.
        painel = montar_visualizacao()
        for p in painel["por_pavimento"]:
            assert p["total_nao_alocado"] == 0
            assert sum(p["nao_alocado"]) == 0
            assert p["alertas"] == []

    def test_obrigatoriedade_problematica_gera_alerta_no_pavimento(self):
        # Força as três clínicas (24 estações de demanda no pico) no pavimento
        # de 12 estações: a obrigatoriedade cria sobra ali, e só ali.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            restricoes = RestricoesService(sessao)
            for unidade in cenario.unidades:
                await restricoes.definir(
                    cenario, unidade.id, cenario.pavimentos[1].id, OBRIGATORIO
                )
            from src.services import AlocacaoService

            await AlocacaoService(sessao).executar(cenario)
            return VisualizacaoService(sessao).montar(cenario)

        painel = executar(rodar)
        pavimentos = {p["id"]: p for p in painel["por_pavimento"]}

        forcado = next(p for p in painel["por_pavimento"] if p["clinicas"])
        assert forcado["total_nao_alocado"] == 12
        assert len(forcado["alertas"]) == 1
        assert forcado["alertas"][0]["tipo"] == "obrigatoriedade_problematica"

        # O outro pavimento, sem ocupantes, não tem sobra nem alerta.
        vazio = next(p for p in painel["por_pavimento"] if not p["clinicas"])
        assert vazio["total_nao_alocado"] == 0
        assert vazio["alertas"] == []

    def test_excesso_sem_obrigatoriedade_gera_alerta_generico(self):
        # Um pavimento pequeno demais para a demanda: o motor deixa grades sem
        # sala sem nenhuma obrigatoriedade por trás — o alerta é "excesso".
        async def rodar(sessao):
            from src.domain.entidades import Clinica
            from src.domain.importacao import GradeDemanda, GradeSlot
            from src.repositories import AlocacaoRepository, PavimentoEntrada
            from src.services import AlocacaoService

            pico = indice_turno("segunda", "manha")
            clinicas = (Clinica(id=1, nome="CARDIOLOGIA", demanda=demanda_em([pico], 10)),)
            slots = (GradeSlot("Dr. Car", "CARDIOLOGIA", "segunda", "manha"),)
            demandas = (GradeDemanda("CARDIOLOGIA", "segunda", "manha", 10),)
            # 4 estações — não cabe a demanda de 10; sobram 6 sem sala.
            pavimentos = (PavimentoEntrada(bloco="Bloco A", nome="Térreo", padrao_1est=4),)

            repo = AlocacaoRepository(sessao)
            cenario = await repo.criar(
                nome="Excesso",
                clinicas=clinicas,
                slots=slots,
                demandas=demandas,
                pavimentos=pavimentos,
                resultado=None,
            )
            cid = cenario.id
            await sessao.commit()
            sessao.expunge_all()

            cenario = await repo.obter(cid)
            await AlocacaoService(sessao).executar(cenario)
            return VisualizacaoService(sessao).montar(cenario)

        painel = executar(rodar)
        afetado = next(
            p
            for p in painel["por_pavimento"]
            if any(c["nome"] == "CARDIOLOGIA" for c in p["clinicas"])
        )
        assert afetado["total_nao_alocado"] == 6
        assert afetado["alertas"] == [
            {
                "tipo": "excesso",
                "mensagem": "Capacidade excedida: 6 grade(s) sem sala neste pavimento.",
            }
        ]


class TestPorTurno:

    def test_um_registro_por_turno(self):
        painel = montar_visualizacao()
        assert len(painel["por_turno"]) == 10

    def test_demanda_bate_com_alocado_mais_sobra(self):
        painel = montar_visualizacao()
        for t in painel["por_turno"]:
            assert t["demanda"] == t["alocado"] + t["nao_alocado"]

    def test_pico_de_demanda_em_segunda_manha(self):
        painel = montar_visualizacao()
        pico = indice_turno("segunda", "manha")
        # A demanda do cenário está toda concentrada em segunda-manhã.
        assert painel["por_turno"][pico]["demanda"] == 24
        for i, t in enumerate(painel["por_turno"]):
            if i != pico:
                assert t["demanda"] == 0


class TestPorClinica:

    def test_uma_linha_por_clinica_participante(self):
        painel = montar_visualizacao()
        assert len(painel["por_clinica"]) == 3
        for c in painel["por_clinica"]:
            assert c["pavimento"] is not None
            assert c["total_alocado"] + c["total_nao_alocado"] > 0

    def test_bloco_e_pavimento_vem_separados_do_completo(self):
        # Bloco e pavimento (nome curto) precisam vir como campos distintos —
        # é o que permite a tela filtrar por cada um independentemente; o
        # completo continua disponível para tooltip/compatibilidade.
        painel = montar_visualizacao()
        for c in painel["por_clinica"]:
            assert c["bloco"]
            assert c["pavimento"]
            assert c["pavimento_completo"] == f"{c['bloco']} — {c['pavimento']}"

    def test_clinicas_com_sobra_vem_primeiro(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            restricoes = RestricoesService(sessao)
            for unidade in cenario.unidades:
                await restricoes.definir(
                    cenario, unidade.id, cenario.pavimentos[1].id, OBRIGATORIO
                )
            from src.services import AlocacaoService

            await AlocacaoService(sessao).executar(cenario)
            return VisualizacaoService(sessao).montar(cenario)

        painel = executar(rodar)
        sobras = [c["total_nao_alocado"] for c in painel["por_clinica"]]
        # Ordenado do maior para o menor: quem tem sobra aparece no topo.
        assert sobras == sorted(sobras, reverse=True)


class TestDesatualizacao:

    def test_painel_sinaliza_execucao_desatualizada(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            # Mexer nas grades desatualiza a alocação, mas o painel continua
            # mostrando o último resultado.
            from src.services import GradesService

            await GradesService(sessao).editar_demanda(
                cenario, cenario.unidades[0].id, "segunda", "manha", 3
            )
            return VisualizacaoService(sessao).montar(cenario)

        painel = executar(rodar)
        assert painel["desatualizada"] is True
