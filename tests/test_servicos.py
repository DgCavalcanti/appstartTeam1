"""
test_servicos.py — Camada de serviços e a máquina de estados das 6 etapas.

O foco é a regra de invalidação: mexer nas grades, nas salas ou nas restrições
não pode apagar a alocação — só avisar que ela pode não valer mais.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.domain.entidades import NUM_TURNOS, OBRIGATORIO, PREFERENCIAL, Clinica, indice_turno
from src.domain.importacao import GradeDemanda, GradeSlot
from src.domain.processo import (
    CONCLUIDA,
    DESATUALIZADA,
    EM_ANDAMENTO,
    PENDENTE,
    PREENCHIDA,
    RASCUNHO,
    etapas_invalidadas_por,
)
from src.repositories import AlocacaoRepository, PavimentoEntrada
from src.resources.database import Base
from src.services import (
    AlocacaoService,
    GradesService,
    PanoramaService,
    ProcessoService,
    RestricoesService,
    pesos_do_motor,
    resolver_regras_padrao,
)


# ---------------------------------------------------------------------------
# Infraestrutura
# ---------------------------------------------------------------------------


def executar(corotina):
    async def _rodar():
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
        )
        try:
            async with engine.begin() as conexao:
                await conexao.run_sync(Base.metadata.create_all)
            fabrica = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with fabrica() as sessao:
                return await corotina(sessao)
        finally:
            await engine.dispose()

    return asyncio.run(_rodar())


def demanda_em(turnos, q: int) -> tuple[int, ...]:
    vetor = [0] * NUM_TURNOS
    for t in turnos:
        vetor[t] = q
    return tuple(vetor)


async def montar_cenario(sessao, *, com_resultado: bool = False):
    """
    Cria um cenário com 3 clínicas e 2 pavimentos e o devolve recarregado.

    A demanda é concentrada em segunda-manhã para os testes de capacidade
    ficarem legíveis.
    """
    pico = indice_turno("segunda", "manha")
    clinicas = (
        Clinica(id=1, nome="CARDIOLOGIA", demanda=demanda_em([pico], 10)),
        Clinica(id=2, nome="ORTOPEDIA", demanda=demanda_em([pico], 8)),
        Clinica(id=3, nome="PEDIATRIA", demanda=demanda_em([pico], 6)),
    )
    slots = tuple(
        GradeSlot(f"Dr. {c.nome[:3]}{i}", c.nome, "segunda", "manha")
        for c in clinicas
        for i in range(2)
    )
    demandas = tuple(
        GradeDemanda(c.nome, "segunda", "manha", c.demanda[pico]) for c in clinicas
    )
    pavimentos = (
        # 20 estações
        PavimentoEntrada(bloco="Bloco A", nome="Térreo", padrao_2est=10),
        # 12 estações
        PavimentoEntrada(bloco="Bloco B", nome="Térreo", padrao_1est=12),
    )

    repo = AlocacaoRepository(sessao)
    cenario = await repo.criar(
        nome="Cenário de teste",
        clinicas=clinicas,
        slots=slots,
        demandas=demandas,
        pavimentos=pavimentos,
        resultado=None,
    )
    cenario_id = cenario.id
    await sessao.commit()
    sessao.expunge_all()

    cenario = await repo.obter(cenario_id)
    if com_resultado:
        await AlocacaoService(sessao).executar(cenario)
        await sessao.commit()
        sessao.expunge_all()
        cenario = await repo.obter(cenario_id)
    return cenario


def status_das_etapas(cenario) -> dict[int, str]:
    return {e.numero: e.status for e in cenario.etapas}


# ---------------------------------------------------------------------------
# A regra de invalidação, isolada
# ---------------------------------------------------------------------------


class TestRegraDeInvalidacao:

    @pytest.mark.parametrize("etapa", [1, 2, 3, 4])
    def test_etapas_de_insumo_invalidam_a_alocacao(self, etapa):
        assert etapas_invalidadas_por(etapa) == frozenset({5, 6})

    def test_executar_nao_invalida_a_si_mesma(self):
        assert etapas_invalidadas_por(5) == frozenset()

    def test_ajustes_manuais_nao_invalidam_nada(self):
        # A etapa 6 edita o resultado da 5 e pode ser acessada a qualquer
        # momento, sem refazer o processo desde o início.
        assert etapas_invalidadas_por(6) == frozenset()

    def test_etapa_fora_do_intervalo(self):
        with pytest.raises(ValueError, match="etapa inválida"):
            etapas_invalidadas_por(7)


# ---------------------------------------------------------------------------
# Máquina de estados
# ---------------------------------------------------------------------------


class TestProcessoService:

    def test_cenario_novo_comeca_como_rascunho(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            return cenario.status, cenario.etapa_atual, status_das_etapas(cenario)

        status, atual, etapas = executar(rodar)
        assert status == RASCUNHO
        assert atual == 1
        assert etapas[1] == PREENCHIDA
        assert etapas[2] == PENDENTE

    def test_alterar_grades_desatualiza_a_alocacao(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            antes = status_das_etapas(cenario)

            invalidadas = await ProcessoService(sessao).registrar_alteracao(cenario, 2)
            return antes, invalidadas, status_das_etapas(cenario)

        antes, invalidadas, depois = executar(rodar)

        assert antes[5] == PREENCHIDA
        assert invalidadas == frozenset({5})
        assert depois[2] == PREENCHIDA
        assert depois[5] == DESATUALIZADA

    def test_o_que_nunca_foi_preenchido_continua_pendente(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)  # sem rodar o motor
            invalidadas = await ProcessoService(sessao).registrar_alteracao(cenario, 3)
            return invalidadas, status_das_etapas(cenario)

        invalidadas, etapas = executar(rodar)
        assert invalidadas == frozenset(), "não há o que invalidar"
        assert etapas[5] == PENDENTE
        assert etapas[6] == PENDENTE

    def test_o_sistema_avisa_em_vez_de_apagar(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            await ProcessoService(sessao).registrar_alteracao(cenario, 4)
            await sessao.commit()
            # O resultado continua no banco, apenas marcado como desatualizado.
            return (
                sum(len(u.resultados) for u in cenario.unidades),
                status_das_etapas(cenario)[5],
            )

        resultados, status = executar(rodar)
        assert resultados > 0, "o resultado não pode ser apagado"
        assert status == DESATUALIZADA

    def test_reexecutar_o_motor_zera_os_ajustes_manuais(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            processo = ProcessoService(sessao)

            # O gestor faz um ajuste manual...
            await processo.registrar_alteracao(cenario, 6)
            apos_ajuste = status_das_etapas(cenario)[6]

            # ...e depois manda rodar o motor de novo.
            await processo.registrar_alteracao(cenario, 5)
            return apos_ajuste, status_das_etapas(cenario)[6]

        apos_ajuste, apos_reexecucao = executar(rodar)
        assert apos_ajuste == PREENCHIDA
        assert apos_reexecucao == PENDENTE, (
            "reexecutar regenera o resultado, então o ajuste manual deixou de existir"
        )

    def test_ajuste_manual_nao_desatualiza_a_execucao(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            await ProcessoService(sessao).registrar_alteracao(cenario, 6)
            return status_das_etapas(cenario)

        etapas = executar(rodar)
        assert etapas[5] == PREENCHIDA
        assert etapas[6] == PREENCHIDA

    def test_status_do_cenario_avanca_com_as_etapas(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            inicial = cenario.status
            await ProcessoService(sessao).registrar_alteracao(cenario, 2)
            return inicial, cenario.status

        inicial, depois = executar(rodar)
        assert inicial == RASCUNHO
        assert depois == EM_ANDAMENTO

    def test_concluir_exige_alocacao_executada(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError, match="não foi executada"):
                await ProcessoService(sessao).concluir(cenario)
            return cenario.status

        assert executar(rodar) == RASCUNHO

    def test_concluir_apos_executar(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            await ProcessoService(sessao).concluir(cenario)
            return cenario.status, cenario.etapa_atual

        status, atual = executar(rodar)
        assert status == CONCLUIDA
        assert atual == 6

    def test_mexer_num_cenario_concluido_o_reabre(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            processo = ProcessoService(sessao)
            await processo.concluir(cenario)
            concluido = cenario.status

            await processo.registrar_alteracao(cenario, 3)
            return concluido, cenario.status

        concluido, depois = executar(rodar)
        assert concluido == CONCLUIDA
        assert depois == EM_ANDAMENTO, (
            "um cenário fechado não pode continuar marcado assim exibindo dados novos"
        )

    def test_ir_para_move_o_ponteiro_sem_mexer_em_status(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            antes = status_das_etapas(cenario)
            await ProcessoService(sessao).ir_para(cenario, 4)
            return cenario.etapa_atual, antes, status_das_etapas(cenario)

        atual, antes, depois = executar(rodar)
        assert atual == 4
        assert antes == depois

    def test_resumo_traz_as_seis_etapas_com_nome(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            return ProcessoService(sessao).resumo(cenario)

        resumo = executar(rodar)
        assert len(resumo) == 6
        assert resumo[0]["nome"] == "Importar grades do AGHU"
        assert resumo[0]["atual"] is True
        assert resumo[1]["atual"] is False


# ---------------------------------------------------------------------------
# Etapa 2 — grades
# ---------------------------------------------------------------------------


class TestGradesService:

    def test_le_a_planilha_com_uma_linha_por_unidade(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            return GradesService(sessao).ler(cenario)

        linhas = executar(rodar)
        assert len(linhas) == 3
        assert all(len(l["demanda"]) == NUM_TURNOS for l in linhas)
        assert {l["nome"] for l in linhas} == {"CARDIOLOGIA", "ORTOPEDIA", "PEDIATRIA"}

    def test_editar_demanda_pode_ultrapassar_o_que_veio_do_aghu(self):
        # O ajuste do gestor é soberano: a importação é ponto de partida,
        # não teto.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = GradesService(sessao)
            await servico.editar_demanda(cenario, cenario.unidades[0].id, "segunda", "manha", 99)
            return {l["nome"]: l["demanda"][0] for l in servico.ler(cenario)}

        demandas = executar(rodar)
        assert demandas["CARDIOLOGIA"] == 99

    def test_editar_cria_a_linha_quando_o_turno_estava_vazio(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = GradesService(sessao)
            await servico.editar_demanda(cenario, cenario.unidades[0].id, "sexta", "tarde", 4)
            return {l["nome"]: l["demanda"][indice_turno("sexta", "tarde")] for l in servico.ler(cenario)}

        assert executar(rodar)["CARDIOLOGIA"] == 4

    def test_editar_desatualiza_a_alocacao(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            await GradesService(sessao).editar_demanda(
                cenario, cenario.unidades[0].id, "segunda", "manha", 5
            )
            return status_das_etapas(cenario)

        assert executar(rodar)[5] == DESATUALIZADA

    def test_quantidade_negativa_e_recusada(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError, match="negativa"):
                await GradesService(sessao).editar_demanda(
                    cenario, cenario.unidades[0].id, "segunda", "manha", -1
                )

        executar(rodar)

    def test_turno_fora_da_malha_e_recusado(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError):
                await GradesService(sessao).editar_demanda(
                    cenario, cenario.unidades[0].id, "sabado", "manha", 1
                )

        executar(rodar)

    def test_tirar_unidade_da_alocacao_solta_o_pavimento(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            unidade = cenario.unidades[0]
            antes = unidade.pavimento_alocado_id
            await GradesService(sessao).definir_participacao(cenario, unidade.id, False)
            return antes, unidade.participa, unidade.pavimento_alocado_id

        antes, participa, depois = executar(rodar)
        assert antes is not None
        assert participa is False
        assert depois is None

    def test_totais_por_turno_ignoram_quem_nao_participa(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = GradesService(sessao)
            com_todas = servico.totais_por_turno(cenario)[0]
            await servico.definir_participacao(cenario, cenario.unidades[0].id, False)
            return com_todas, servico.totais_por_turno(cenario)[0]

        com_todas, sem_uma = executar(rodar)
        assert com_todas == 24  # 10 + 8 + 6
        assert sem_uma == 14    # CARDIOLOGIA saiu

    def test_unidade_de_outro_cenario(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError, match="não pertence"):
                await GradesService(sessao).definir_participacao(cenario, 9999, False)

        executar(rodar)


# ---------------------------------------------------------------------------
# Etapa 3 — panorama de salas
# ---------------------------------------------------------------------------


class TestPanoramaService:

    def test_capacidade_e_derivada_das_contagens(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = PanoramaService(sessao)
            return servico.ler(cenario), servico.capacidade_total(cenario)

        pavimentos, total = executar(rodar)
        assert pavimentos[0]["capacidade"] == 20  # 10 salas de 2 estações
        assert pavimentos[1]["capacidade"] == 12  # 12 salas de 1 estação
        assert total == 32

    def test_editar_recalcula_a_capacidade(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = PanoramaService(sessao)
            pavimento = await servico.editar(
                cenario, cenario.pavimentos[0].id, {"padrao_2est": 15}
            )
            return pavimento.capacidade

        assert executar(rodar) == 30

    def test_edicao_parcial_preserva_os_outros_campos(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = PanoramaService(sessao)
            await servico.editar(cenario, cenario.pavimentos[0].id, {"esp_1est": 3})
            p = servico.ler(cenario)[0]
            return p["padrao_2est"], p["esp_1est"], p["capacidade"]

        padrao, esp, capacidade = executar(rodar)
        assert padrao == 10, "o campo não informado não pode ser zerado"
        assert esp == 3
        assert capacidade == 23

    def test_salas_fechadas_nao_contam_na_capacidade(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = PanoramaService(sessao)
            pavimento = await servico.editar(
                cenario, cenario.pavimentos[0].id, {"fechada": 5}
            )
            return pavimento.capacidade, pavimento.fechada

        capacidade, fechadas = executar(rodar)
        assert capacidade == 20
        assert fechadas == 5

    def test_campo_desconhecido_e_recusado(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError, match="campos desconhecidos"):
                await PanoramaService(sessao).editar(
                    cenario, cenario.pavimentos[0].id, {"capacidade": 99}
                )

        executar(rodar)

    def test_editar_desatualiza_a_alocacao(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            await PanoramaService(sessao).editar(
                cenario, cenario.pavimentos[0].id, {"padrao_2est": 2}
            )
            return status_das_etapas(cenario)

        assert executar(rodar)[5] == DESATUALIZADA


# ---------------------------------------------------------------------------
# Etapa 4 — restrições
# ---------------------------------------------------------------------------


class TestRestricoesService:

    def test_definir_obrigatoriedade(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = RestricoesService(sessao)
            await servico.definir(
                cenario, cenario.unidades[0].id, cenario.pavimentos[0].id, OBRIGATORIO
            )
            return servico.listar(cenario)

        restricoes = executar(rodar)
        assert len(restricoes) == 1
        assert restricoes[0]["tipo"] == OBRIGATORIO

    def test_uma_unidade_so_pode_ter_uma_obrigatoriedade(self):
        # Ela fica num pavimento só na semana inteira: duas travas seriam
        # contraditórias.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = RestricoesService(sessao)
            unidade = cenario.unidades[0].id
            await servico.definir(cenario, unidade, cenario.pavimentos[0].id, OBRIGATORIO)
            await servico.definir(cenario, unidade, cenario.pavimentos[1].id, OBRIGATORIO)
            return servico.listar(cenario)

        restricoes = executar(rodar)
        assert len(restricoes) == 1
        assert restricoes[0]["pavimento"] == "Bloco B — Térreo"

    def test_preferencias_podem_coexistir_com_obrigatoriedade(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = RestricoesService(sessao)
            unidade = cenario.unidades[0].id
            await servico.definir(cenario, unidade, cenario.pavimentos[0].id, OBRIGATORIO)
            await servico.definir(cenario, unidade, cenario.pavimentos[1].id, PREFERENCIAL)
            return sorted(r["tipo"] for r in servico.listar(cenario))

        assert executar(rodar) == [OBRIGATORIO, PREFERENCIAL]

    def test_definir_a_mesma_restricao_duas_vezes_nao_duplica(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = RestricoesService(sessao)
            for _ in range(2):
                await servico.definir(
                    cenario, cenario.unidades[0].id, cenario.pavimentos[0].id, PREFERENCIAL
                )
            return len(servico.listar(cenario))

        assert executar(rodar) == 1

    def test_tipo_invalido(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            with pytest.raises(ValueError, match="tipo inválido"):
                await RestricoesService(sessao).definir(
                    cenario, cenario.unidades[0].id, cenario.pavimentos[0].id, "talvez"
                )

        executar(rodar)

    def test_remover(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = RestricoesService(sessao)
            restricao = await servico.definir(
                cenario, cenario.unidades[0].id, cenario.pavimentos[0].id, PREFERENCIAL
            )
            await sessao.flush()
            removida = await servico.remover(cenario, restricao.id)
            return removida, servico.listar(cenario)

        removida, restantes = executar(rodar)
        assert removida is True
        assert restantes == []

    def test_remover_inexistente(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            return await RestricoesService(sessao).remover(cenario, 9999)

        assert executar(rodar) is False


# ---------------------------------------------------------------------------
# Etapa 5 — executar o motor sobre o cenário salvo
# ---------------------------------------------------------------------------


class TestAlocacaoService:

    def test_executa_e_grava_o_resultado(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            resultado = await AlocacaoService(sessao).executar(cenario)
            return (
                resultado.total_alocado,
                resultado.total_nao_alocado,
                [(u.unidade_nome, u.pavimento_alocado_id) for u in cenario.unidades],
            )

        alocado, sobra, destinos = executar(rodar)
        assert alocado == 24, "10 + 8 + 6 grades cabem nos dois pavimentos"
        assert sobra == 0
        assert all(pav is not None for _, pav in destinos)

    def test_obrigatoriedade_e_respeitada_e_pode_gerar_sobra(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            restricoes = RestricoesService(sessao)
            # As três clínicas (24 grades) forçadas no pavimento de 12 estações.
            for unidade in cenario.unidades:
                await restricoes.definir(
                    cenario, unidade.id, cenario.pavimentos[1].id, OBRIGATORIO
                )
            resultado = await AlocacaoService(sessao).executar(cenario)
            return resultado.total_alocado, resultado.total_nao_alocado, {
                u.unidade_nome: u.pavimento_alocado_id for u in cenario.unidades
            }

        alocado, sobra, destinos = executar(rodar)
        assert alocado == 12, "a capacidade do pavimento forçado"
        assert sobra == 12
        assert len(set(destinos.values())) == 1, "todas no mesmo pavimento"

    def test_preferencia_atrai_sem_gerar_sobra(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            unidade = next(u for u in cenario.unidades if u.unidade_nome == "PEDIATRIA")
            preferido = cenario.pavimentos[1].id
            await RestricoesService(sessao).definir(
                cenario, unidade.id, preferido, PREFERENCIAL
            )
            resultado = await AlocacaoService(sessao).executar(cenario)
            return unidade.pavimento_alocado_id, preferido, resultado.total_nao_alocado

        destino, preferido, sobra = executar(rodar)
        assert destino == preferido
        assert sobra == 0

    def test_reexecutar_substitui_o_resultado_sem_acumular(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            servico = AlocacaoService(sessao)
            await servico.executar(cenario)
            primeira = sum(len(u.resultados) for u in cenario.unidades)
            await servico.executar(cenario)
            return primeira, sum(len(u.resultados) for u in cenario.unidades)

        primeira, segunda = executar(rodar)
        assert primeira == segunda

    def test_unidade_fora_da_alocacao_nao_entra(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            unidade = cenario.unidades[0]
            await GradesService(sessao).definir_participacao(cenario, unidade.id, False)
            resultado = await AlocacaoService(sessao).executar(cenario)
            return (
                resultado.total_alocado,
                unidade.pavimento_alocado_id,
                len(resultado.por_clinica),
            )

        alocado, pavimento, clinicas = executar(rodar)
        assert clinicas == 2
        assert alocado == 14, "sem CARDIOLOGIA restam 8 + 6"
        assert pavimento is None

    def test_cenario_sem_participantes(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            grades = GradesService(sessao)
            for unidade in cenario.unidades:
                await grades.definir_participacao(cenario, unidade.id, False)
            with pytest.raises(ValueError, match="nenhuma unidade participante"):
                await AlocacaoService(sessao).executar(cenario)

        executar(rodar)

    def test_executar_marca_a_etapa_5(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao)
            await AlocacaoService(sessao).executar(cenario)
            return status_das_etapas(cenario), cenario.status

        etapas, status = executar(rodar)
        assert etapas[5] == PREENCHIDA
        assert status == EM_ANDAMENTO

    def test_reexecucao_preserva_ajuste_manual_quando_a_solucao_empata(self):
        # Fase 2, nível 6 da hierarquia: `alocacao_atual` vem de
        # `pavimento_alocado_id`, e o motor não distingue se ele foi escrito
        # por uma execução automática anterior ou por `mover()` (ajuste
        # manual, etapa 6) — as duas são tratadas igual. Cenário simétrico:
        # duas clínicas idênticas, dois pavimentos idênticos, sem afinidade —
        # qualquer das duas alocações possíveis é igualmente ótima nos níveis
        # 1 a 5. O gestor troca manualmente as duas de lugar; reexecutar não
        # pode desfazer a troca, porque o resultado manual é tão bom quanto
        # o automático e a estabilidade desempata a favor dele.
        async def rodar(sessao):
            pico = indice_turno("segunda", "manha")
            clinicas = (
                Clinica(id=1, nome="ALPHA", demanda=demanda_em([pico], 5)),
                Clinica(id=2, nome="BETA", demanda=demanda_em([pico], 5)),
            )
            slots = tuple(
                GradeSlot(f"Dr. {c.nome[:3]}", c.nome, "segunda", "manha")
                for c in clinicas
            )
            demandas = tuple(
                GradeDemanda(c.nome, "segunda", "manha", c.demanda[pico])
                for c in clinicas
            )
            pavimentos = (
                PavimentoEntrada(bloco="Bloco A", nome="Térreo", padrao_1est=5),
                PavimentoEntrada(bloco="Bloco B", nome="Térreo", padrao_1est=5),
            )

            repo = AlocacaoRepository(sessao)
            criado = await repo.criar(
                nome="Simétrico",
                clinicas=clinicas,
                slots=slots,
                demandas=demandas,
                pavimentos=pavimentos,
                resultado=None,
            )
            cenario_id = criado.id
            await sessao.commit()
            sessao.expunge_all()
            cenario = await repo.obter(cenario_id)

            servico = AlocacaoService(sessao)
            await servico.executar(cenario)
            await sessao.commit()

            alpha = next(u for u in cenario.unidades if u.unidade_nome == "ALPHA")
            beta = next(u for u in cenario.unidades if u.unidade_nome == "BETA")
            pav_alpha_original = alpha.pavimento_alocado_id
            pav_beta_original = beta.pavimento_alocado_id
            assert pav_alpha_original != pav_beta_original

            # Ajuste manual: troca as duas de pavimento.
            await servico.mover(cenario, alpha.id, pav_beta_original)
            await servico.mover(cenario, beta.id, pav_alpha_original)
            await sessao.commit()

            # Reexecuta o motor sobre o cenário já ajustado à mão.
            await servico.executar(cenario)

            return (
                alpha.pavimento_alocado_id,
                beta.pavimento_alocado_id,
                pav_alpha_original,
                pav_beta_original,
            )

        pav_alpha_depois, pav_beta_depois, pav_alpha_original, pav_beta_original = executar(
            rodar
        )
        assert pav_alpha_depois == pav_beta_original, (
            "a troca manual deveria sobreviver à reexecução — o motor não pode "
            "desfazer um ajuste que é tão bom quanto o automático"
        )
        assert pav_beta_depois == pav_alpha_original


# ---------------------------------------------------------------------------
# Etapa 6 — ajustes manuais
# ---------------------------------------------------------------------------


class TestAjustesManuais:

    def test_mover_troca_o_pavimento_da_clinica(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            unidade = next(u for u in cenario.unidades if u.unidade_nome == "CARDIOLOGIA")
            destino = cenario.pavimentos[1]  # Bloco B
            await AlocacaoService(sessao).mover(cenario, unidade.id, destino.id)
            return unidade.pavimento_alocado_id, destino.id

        alocado, destino_id = executar(rodar)
        assert alocado == destino_id

    def test_mover_deixa_a_clinica_totalmente_alocada(self):
        # "Aceitar e só avisar": a clínica vai inteira para o destino — nada de
        # "sem sala" por clínica; a sobrecarga vira aviso derivado na tela.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            unidade = next(u for u in cenario.unidades if u.unidade_nome == "CARDIOLOGIA")
            await AlocacaoService(sessao).mover(
                cenario, unidade.id, cenario.pavimentos[1].id
            )
            registro = next(
                r
                for r in unidade.resultados
                if r.dia_semana == "segunda" and r.turno == "manha"
            )
            return registro.qtd_alocada, registro.qtd_nao_alocada

        alocada, nao_alocada = executar(rodar)
        assert alocada == 10, "a demanda inteira (10) fica no destino"
        assert nao_alocada == 0

    def test_mover_para_pavimento_sobrecarregado_e_permitido(self):
        # Bloco B tem 12 estações; juntar CARDIOLOGIA (10) e ORTOPEDIA (8) = 18
        # estoura a capacidade — mas o gestor pode; o sistema não bloqueia.
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            servico = AlocacaoService(sessao)
            bloco_b = cenario.pavimentos[1].id
            for nome in ("CARDIOLOGIA", "ORTOPEDIA"):
                u = next(x for x in cenario.unidades if x.unidade_nome == nome)
                await servico.mover(cenario, u.id, bloco_b)
            return [
                u.pavimento_alocado_id
                for u in cenario.unidades
                if u.unidade_nome in ("CARDIOLOGIA", "ORTOPEDIA")
            ], bloco_b

        pavimentos, bloco_b = executar(rodar)
        assert pavimentos == [bloco_b, bloco_b]

    def test_mover_unidade_inexistente_e_recusado(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            with pytest.raises(ValueError, match="não pertence"):
                await AlocacaoService(sessao).mover(
                    cenario, 999999, cenario.pavimentos[0].id
                )

        executar(rodar)

    def test_mover_para_pavimento_inexistente_e_recusado(self):
        async def rodar(sessao):
            cenario = await montar_cenario(sessao, com_resultado=True)
            with pytest.raises(ValueError, match="não pertence"):
                await AlocacaoService(sessao).mover(
                    cenario, cenario.unidades[0].id, 999999
                )

        executar(rodar)


# ---------------------------------------------------------------------------
# Regras padrão → pesos do motor (pré-alocação)
# ---------------------------------------------------------------------------


@dataclass
class _PavimentoCatalogoFalso:
    """Dublê do relacionamento `RestricaoPadrao.pavimento` — só bloco/nome."""

    bloco: str
    nome: str


@dataclass
class _RegraPadraoFalsa:
    """Dublê de `RestricaoPadrao` — as duas funções só leem estes 3 campos."""

    unidade_normalizada: str
    tipo: str
    pavimento: _PavimentoCatalogoFalso


class TestResolverRegrasPadrao:

    def test_casa_pelo_par_bloco_nome(self):
        regra = _RegraPadraoFalsa(
            unidade_normalizada="cardiologia",
            tipo=OBRIGATORIO,
            pavimento=_PavimentoCatalogoFalso(bloco="Bloco E", nome="2º Pavimento"),
        )
        pavimentos = [("Bloco D", "3º Pavimento"), ("Bloco E", "2º Pavimento")]

        resolvidas = resolver_regras_padrao([regra], pavimentos)

        assert resolvidas == (("cardiologia", 2, OBRIGATORIO),)

    def test_regra_sem_pavimento_correspondente_e_ignorada(self):
        regra = _RegraPadraoFalsa(
            unidade_normalizada="cardiologia",
            tipo=OBRIGATORIO,
            pavimento=_PavimentoCatalogoFalso(bloco="Bloco Z", nome="9º Pavimento"),
        )
        pavimentos = [("Bloco D", "3º Pavimento")]

        assert resolver_regras_padrao([regra], pavimentos) == ()

    def test_sem_regras_devolve_vazio(self):
        assert resolver_regras_padrao([], [("Bloco D", "3º Pavimento")]) == ()


class TestPesosDoMotor:

    def test_obrigatoriedade_vira_entrada_no_dict(self):
        clinicas = (Clinica(id=1, nome="CARDIOLOGIA", demanda=(0,) * NUM_TURNOS),)
        regras = (("cardiologia", 2, OBRIGATORIO),)

        obrigatorias, afinidade = pesos_do_motor(regras, clinicas)

        assert obrigatorias == {1: 2}
        assert afinidade == {}

    def test_preferencial_vira_afinidade(self):
        clinicas = (Clinica(id=1, nome="CARDIOLOGIA", demanda=(0,) * NUM_TURNOS),)
        regras = (("cardiologia", 3, PREFERENCIAL),)

        obrigatorias, afinidade = pesos_do_motor(regras, clinicas)

        assert obrigatorias == {}
        assert afinidade == {(1, 3): pytest.approx(1.0)}

    def test_unidade_sem_clinica_correspondente_e_ignorada(self):
        # A regra padrão pode referenciar uma unidade que não está entre as
        # clínicas deste cálculo (ex.: não participa deste cenário/prévia).
        clinicas = (Clinica(id=1, nome="ORTOPEDIA", demanda=(0,) * NUM_TURNOS),)
        regras = (("cardiologia", 1, OBRIGATORIO),)

        obrigatorias, afinidade = pesos_do_motor(regras, clinicas)

        assert obrigatorias == {}
        assert afinidade == {}

    def test_casamento_e_por_forma_normalizada(self):
        # A clínica carrega o nome original ("CARDIOLOGIA (AMBULATÓRIO)"); a
        # regra guarda a forma normalizada. O casamento tem que atravessar isso.
        clinicas = (
            Clinica(id=7, nome="Cardiologia (Ambulatório)", demanda=(0,) * NUM_TURNOS),
        )
        regras = (("cardiologia (ambulatorio)", 1, OBRIGATORIO),)

        obrigatorias, _ = pesos_do_motor(regras, clinicas)

        assert obrigatorias == {7: 1}
