"""
test_solver_heuristico.py — Testes do motor de alocação (clínica → pavimento).

Cobre as regras da seção 8 do SAA_Arquitetura.pdf e reproduz os três cenários
de validação que o documento registra sobre os dados reais do HC.
"""

from __future__ import annotations

import pytest

from src.domain.alocacao import (
    EntradaAlocacao,
    SolverHeuristico,
    repartir_turno,
)
from src.domain.entidades import (
    NUM_TURNOS,
    OBRIGATORIO,
    PREFERENCIAL,
    Clinica,
    Pavimento,
    Restricao,
    capacidade_do_pool,
    capacidade_em_estacoes,
    indice_turno,
    pool_da_clinica,
    salas_ocupadas,
    total_de_salas,
)


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------

#: Turnos de manhã ocupam os índices pares; os de tarde, os ímpares.
MANHAS = tuple(range(0, NUM_TURNOS, 2))
TARDES = tuple(range(1, NUM_TURNOS, 2))


def demanda_uniforme(q: int) -> tuple[int, ...]:
    """Mesma demanda nos 10 turnos."""
    return (q,) * NUM_TURNOS


def demanda_em(turnos, q: int) -> tuple[int, ...]:
    """Demanda `q` apenas nos turnos indicados; zero no resto."""
    vetor = [0] * NUM_TURNOS
    for t in turnos:
        vetor[t] = q
    return tuple(vetor)


def resolver(**kwargs) -> object:
    return SolverHeuristico().resolver(EntradaAlocacao(**kwargs))


# ---------------------------------------------------------------------------
# Malha de turnos e capacidade
# ---------------------------------------------------------------------------


class TestMalhaDeTurnos:

    def test_dez_turnos(self):
        assert NUM_TURNOS == 10

    def test_indice_turno_ordem_canonica(self):
        assert indice_turno("segunda", "manha") == 0
        assert indice_turno("segunda", "tarde") == 1
        assert indice_turno("terca", "manha") == 2
        assert indice_turno("sexta", "tarde") == 9

    def test_indice_turno_normaliza_caixa_e_espacos(self):
        assert indice_turno("  SEGUNDA ", "Manha") == 0

    def test_sabado_e_noite_sao_rejeitados(self):
        # Ambos são descartados no pipeline de importação (seção 6).
        with pytest.raises(ValueError):
            indice_turno("sabado", "manha")
        with pytest.raises(ValueError):
            indice_turno("segunda", "noite")


class TestCapacidade:

    def test_sala_de_duas_estacoes_vale_dois(self):
        assert capacidade_em_estacoes(padrao_2est=3) == 6
        assert capacidade_em_estacoes(esp_2est=3) == 6

    def test_formula_completa(self):
        # 1×PADRÃO(1est) + 2×PADRÃO(2est) + 1×ESP(1est) + 2×ESP(2est)
        assert capacidade_em_estacoes(
            padrao_1est=4, padrao_2est=2, esp_1est=1, esp_2est=3
        ) == 4 + 4 + 1 + 6

    def test_relatorio_converte_de_volta_para_salas_fisicas(self):
        contagens = dict(padrao_1est=4, padrao_2est=2, esp_1est=1, esp_2est=3)
        assert capacidade_em_estacoes(**contagens) == 15
        assert total_de_salas(**contagens) == 10


class TestSalasOcupadas:
    """Conversão de estações em uso para salas físicas (seção 14)."""

    def test_sem_ocupacao_nenhuma_sala(self):
        assert salas_ocupadas(0, padrao_2est=5) == 0

    def test_sala_de_duas_estacoes_parcial_conta_como_uma(self):
        # 1 estação usada num pavimento só de salas de 2 estações ocupa 1 sala.
        assert salas_ocupadas(1, padrao_2est=5) == 1
        assert salas_ocupadas(2, padrao_2est=5) == 1
        assert salas_ocupadas(3, padrao_2est=5) == 2

    def test_salas_de_uma_estacao(self):
        assert salas_ocupadas(3, padrao_1est=10) == 3

    def test_preenche_as_de_duas_estacoes_primeiro(self):
        # Pavimento: duas de 2est + duas de 1est (6 estações, 4 salas).
        contagens = dict(padrao_2est=2, padrao_1est=2)
        # 5 estações: 2+2 nas de 2est, +1 numa de 1est = 3 salas.
        assert salas_ocupadas(5, **contagens) == 3
        # A capacidade toda em uso ocupa todas as 4 salas.
        assert salas_ocupadas(6, **contagens) == 4

    def test_nao_infla_alem_das_salas_existentes(self):
        # Sob obrigatoriedade a ocupação pode passar da capacidade; ainda assim
        # não há mais salas físicas do que as que existem.
        assert salas_ocupadas(99, padrao_2est=3) == 3


# ---------------------------------------------------------------------------
# Repartição proporcional da sobra
# ---------------------------------------------------------------------------


class TestRepartirTurno:

    def test_exemplo_do_documento(self):
        # Validação registrada no PDF: Pediatria pede 17 e Oncologia 13 num
        # pavimento de 9 estações → 5 e 4, cada uma mantendo ~30%.
        assert repartir_turno([17, 13], 9) == [5, 4]

    def test_quando_cabe_todos_recebem_tudo(self):
        assert repartir_turno([3, 4], 10) == [3, 4]

    def test_capacidade_exata(self):
        assert repartir_turno([5, 5], 10) == [5, 5]

    def test_capacidade_zero_nao_aloca_nada(self):
        assert repartir_turno([3, 2], 0) == [0, 0]

    def test_pavimento_vazio(self):
        assert repartir_turno([], 5) == []

    def test_nunca_distribui_mais_que_a_capacidade(self):
        assert sum(repartir_turno([10, 10, 10], 7)) == 7

    def test_nunca_da_a_ninguem_mais_do_que_pediu(self):
        recebido = repartir_turno([1, 20], 9)
        assert recebido[0] <= 1
        assert sum(recebido) == 9

    def test_fracoes_ficam_proximas_entre_si(self):
        demandas = [17, 13, 11]
        recebido = repartir_turno(demandas, 12)
        fracoes = [r / d for r, d in zip(recebido, demandas)]
        assert max(fracoes) - min(fracoes) < 0.10


# ---------------------------------------------------------------------------
# Cenário 1 do documento — baseline sem restrições
# ---------------------------------------------------------------------------


class TestBaselineSemRestricoes:
    """Havendo espaço, o motor não pode deixar nenhuma grade de fora."""

    def test_sem_restricoes_nao_sobra_nada(self):
        clinicas = tuple(
            Clinica(id=i, nome=f"Clínica {i}", demanda=demanda_uniforme(5))
            for i in range(1, 7)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"Pavimento {i}", capacidade=10) for i in range(1, 4)
        )

        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert resultado.total_nao_alocado == 0
        assert resultado.total_alocado == sum(c.total for c in clinicas)

    def test_encaixe_no_limite_exato(self):
        # 3 clínicas de 10 estações em 3 pavimentos de 10: cabe, sem folga.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(10))
            for i in range(1, 4)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"P{i}", capacidade=10) for i in range(1, 4)
        )

        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert resultado.total_nao_alocado == 0
        destinos = {r.pavimento_id for r in resultado.por_clinica}
        assert len(destinos) == 3, "cada clínica deveria ocupar um pavimento distinto"

    def test_clinicas_complementares_dividem_o_pavimento(self):
        # Uma cheia de manhã e uma cheia de tarde ocupam bem a mesma caixa —
        # é exatamente o que o empacotamento vetorial deve encontrar.
        manha = Clinica(id=1, nome="Só de manhã", demanda=demanda_em(MANHAS, 10))
        tarde = Clinica(id=2, nome="Só de tarde", demanda=demanda_em(TARDES, 10))
        pavimentos = (Pavimento(id=1, nome="Único", capacidade=10),)

        resultado = resolver(clinicas=(manha, tarde), pavimentos=pavimentos)

        assert resultado.total_nao_alocado == 0
        assert resultado.pavimento_da_clinica(1) == resultado.pavimento_da_clinica(2)


# ---------------------------------------------------------------------------
# Cenário 2 do documento — obrigatoriedade forçada
# ---------------------------------------------------------------------------


class TestObrigatoriedade:
    """Só a obrigatoriedade força — e é a única coisa capaz de gerar sobra."""

    def test_pediatria_e_oncologia_no_pavimento_de_nove_estacoes(self):
        # Reprodução do cenário do PDF: as duas clínicas são forçadas para o
        # mesmo pavimento de 9 estações. No pico (segunda-manhã) Pediatria pede
        # 17 e fica com 5; Oncologia pede 13 e fica com 4.
        pico = indice_turno("segunda", "manha")
        pediatria = Clinica(id=1, nome="Pediatria", demanda=demanda_em([pico], 17))
        oncologia = Clinica(id=2, nome="Oncologia", demanda=demanda_em([pico], 13))

        apertado = Pavimento(id=1, nome="Pavimento de 9", capacidade=9)
        folgado = Pavimento(id=2, nome="Pavimento amplo", capacidade=40)

        resultado = resolver(
            clinicas=(pediatria, oncologia),
            pavimentos=(apertado, folgado),
            obrigatorias={1: apertado.id, 2: apertado.id},
        )

        assert resultado.pavimento_da_clinica(1) == apertado.id
        assert resultado.pavimento_da_clinica(2) == apertado.id

        por_id = {r.clinica_id: r for r in resultado.por_clinica}
        assert por_id[1].alocado[pico] == 5
        assert por_id[2].alocado[pico] == 4
        assert por_id[1].alocado[pico] + por_id[2].alocado[pico] == apertado.capacidade

        # A sobra é o que não coube: 30 pedidas, 9 atendidas.
        assert resultado.total_nao_alocado == 21

    def test_a_sobra_e_repartida_na_mesma_fracao(self):
        pico = indice_turno("segunda", "manha")
        pediatria = Clinica(id=1, nome="Pediatria", demanda=demanda_em([pico], 17))
        oncologia = Clinica(id=2, nome="Oncologia", demanda=demanda_em([pico], 13))
        apertado = Pavimento(id=1, nome="Pavimento de 9", capacidade=9)

        resultado = resolver(
            clinicas=(pediatria, oncologia),
            pavimentos=(apertado,),
            obrigatorias={1: 1, 2: 1},
        )

        por_id = {r.clinica_id: r for r in resultado.por_clinica}
        fracao_pediatria = por_id[1].alocado[pico] / 17
        fracao_oncologia = por_id[2].alocado[pico] / 13

        assert abs(fracao_pediatria - fracao_oncologia) < 0.05
        assert 0.25 < fracao_pediatria < 0.35

    def test_clinica_obrigatoria_nunca_e_movida_pela_melhoria(self):
        # A obrigatória fica no pavimento apertado mesmo havendo um vazio ao lado.
        presa = Clinica(id=1, nome="Presa", demanda=demanda_uniforme(20))
        apertado = Pavimento(id=1, nome="Apertado", capacidade=5)
        vazio = Pavimento(id=2, nome="Vazio", capacidade=50)

        resultado = resolver(
            clinicas=(presa,),
            pavimentos=(apertado, vazio),
            obrigatorias={1: apertado.id},
        )

        assert resultado.pavimento_da_clinica(1) == apertado.id
        assert resultado.total_nao_alocado == (20 - 5) * NUM_TURNOS


# ---------------------------------------------------------------------------
# Cenário 3 do documento — preferência
# ---------------------------------------------------------------------------


class TestPreferencia:
    """A preferência é um puxão, nunca uma imposição."""

    def test_clinica_vai_para_o_pavimento_preferido(self):
        clinica = Clinica(id=1, nome="Dermatologia", demanda=demanda_uniforme(4))
        pav_a = Pavimento(id=1, nome="A", capacidade=10)
        pav_b = Pavimento(id=2, nome="B", capacidade=10)

        resultado = resolver(
            clinicas=(clinica,),
            pavimentos=(pav_a, pav_b),
            afinidade={(1, pav_b.id): 1.0},
        )

        assert resultado.pavimento_da_clinica(1) == pav_b.id
        assert resultado.total_nao_alocado == 0

    def test_preferencia_cede_quando_o_pavimento_esta_cheio(self):
        # A grande ocupa o pavimento preferido primeiro; a pequena prefere o
        # mesmo lugar, mas não cabe — e vai para o lado em vez de perder grades.
        grande = Clinica(id=1, nome="Grande", demanda=demanda_uniforme(10))
        pequena = Clinica(id=2, nome="Pequena", demanda=demanda_uniforme(4))

        disputado = Pavimento(id=1, nome="Disputado", capacidade=10)
        alternativo = Pavimento(id=2, nome="Alternativo", capacidade=10)

        resultado = resolver(
            clinicas=(grande, pequena),
            pavimentos=(disputado, alternativo),
            afinidade={(1, disputado.id): 1.0, (2, disputado.id): 1.0},
        )

        assert resultado.pavimento_da_clinica(1) == disputado.id
        assert resultado.pavimento_da_clinica(2) == alternativo.id
        assert resultado.total_nao_alocado == 0, (
            "um simples desejo nunca pode fazer uma clínica perder atendimentos "
            "havendo espaço ao lado"
        )

    def test_afinidade_desempata_sem_criar_sobra(self):
        # Duas opções servem; a de maior afinidade vence, e ninguém perde grade.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(5))
            for i in range(1, 3)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"P{i}", capacidade=10) for i in range(1, 4)
        )

        resultado = resolver(
            clinicas=clinicas,
            pavimentos=pavimentos,
            afinidade={(1, 3): 5.0, (2, 3): 0.0},
        )

        assert resultado.pavimento_da_clinica(1) == 3
        assert resultado.total_nao_alocado == 0


# ---------------------------------------------------------------------------
# Cenário 4 (Fase 2) — equilíbrio proporcional
# ---------------------------------------------------------------------------


class TestEquilibrioProporcional:
    """
    Nível 4/5 da hierarquia: sem obrigatoriedade nem afinidade em jogo, o
    motor deve espalhar a carga proporcionalmente à capacidade, não
    concentrar num pavimento até estourar antes de abrir outro (causa raiz
    diagnosticada na Fase 1 em `_folga_residual` como desempate principal).
    """

    def test_nao_concentra_com_capacidades_iguais(self):
        # 6 clínicas de 6 (36/turno) em 3 pavimentos de 20 (60 de capacidade
        # total): cabe tudo sem sobra. A distribuição proporcional ideal é
        # 12/12/12 (60% em cada) — nunca um pavimento vazio com os outros
        # apertados.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(6))
            for i in range(1, 7)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"P{i}", capacidade=20) for i in range(1, 4)
        )

        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert resultado.total_nao_alocado == 0
        ocupacoes = [p.ocupacao_media for p in resultado.por_pavimento]
        assert min(ocupacoes) > 0.0, (
            "nenhum pavimento pode ficar vazio quando dá para espalhar a carga"
        )
        assert max(ocupacoes) - min(ocupacoes) < 0.05

    def test_obrigatoriedade_concentradora_nao_desequilibra_o_resto(self):
        # Duas clínicas presas no mesmo pavimento (obrigatoriedade, nível 1) —
        # as demais, livres, ainda devem se equilibrar entre os pavimentos
        # restantes em vez de amontoar tudo num só.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(5))
            for i in range(1, 7)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"P{i}", capacidade=15) for i in range(1, 4)
        )

        resultado = resolver(
            clinicas=clinicas, pavimentos=pavimentos, obrigatorias={1: 1, 2: 1}
        )

        assert resultado.total_nao_alocado == 0
        ocupacoes = {p.pavimento_id: p.ocupacao_media for p in resultado.por_pavimento}
        # Os dois pavimentos livres (2 e 3) devem ficar igualmente ocupados.
        assert abs(ocupacoes[2] - ocupacoes[3]) < 0.05

    def test_preferencia_vence_equilibrio_mas_nao_afunda_o_resto(self):
        # Nível 3 (afinidade) decide antes do nível 4 (equilíbrio): o
        # pavimento preferido enche primeiro. Mas as clínicas que não
        # couberam lá devem se equilibrar entre os pavimentos restantes —
        # não amontoar todas no primeiro que sobrar.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(5))
            for i in range(1, 7)
        )
        pavimentos = tuple(
            Pavimento(id=i, nome=f"P{i}", capacidade=15) for i in range(1, 4)
        )
        afinidade = {(i, 1): 1.0 for i in range(1, 7)}

        resultado = resolver(
            clinicas=clinicas, pavimentos=pavimentos, afinidade=afinidade
        )

        assert resultado.total_nao_alocado == 0
        ocupacoes = {p.pavimento_id: p.ocupacao_media for p in resultado.por_pavimento}
        # P1 (preferido) fica cheio — cabem 3 das 6 clínicas de 5 estações.
        assert ocupacoes[1] == pytest.approx(1.0)
        # As 3 restantes (2 e 1) se dividem entre P2 e P3: nenhum fica vazio.
        assert min(ocupacoes[2], ocupacoes[3]) > 0.0

    def test_pavimento_de_capacidade_zero_nunca_recebe_clinica(self):
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(4))
            for i in range(1, 3)
        )
        pavimentos = (
            Pavimento(id=1, nome="Ativo", capacidade=20),
            Pavimento(id=2, nome="Fechado", capacidade=0),
        )

        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert resultado.total_nao_alocado == 0
        assert all(r.pavimento_id == 1 for r in resultado.por_clinica)
        ocupacao_fechado = next(
            p for p in resultado.por_pavimento if p.pavimento_id == 2
        )
        assert sum(ocupacao_fechado.ocupacao) == 0


# ---------------------------------------------------------------------------
# Cenário 5 (Fase 2) — preservação da alocação atual (nível 6)
# ---------------------------------------------------------------------------


class TestPreservacaoDaAlocacaoAtual:
    """
    Nível 6: preferência de estabilidade, a de menor prioridade — só desempata
    quando sobra, afinidade e equilíbrio proporcional já empataram entre si.
    """

    def test_alocacao_atual_desempata_entre_solucoes_igualmente_boas(self):
        # Cenário simétrico: 4 clínicas idênticas, 2 pavimentos idênticos —
        # qualquer par de 2+2 é igualmente ótimo nos níveis 1 a 5. A
        # alocação atual deve decidir qual par vence.
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(5))
            for i in range(1, 5)
        )
        pavimentos = (
            Pavimento(id=1, nome="P1", capacidade=10),
            Pavimento(id=2, nome="P2", capacidade=10),
        )
        # A "atual" já tem 1,2 no P2 e 3,4 no P1 — o oposto do que a colocação
        # gulosa (sem estabilidade) tenderia a escolher pela ordem natural.
        atual = {1: 2, 2: 2, 3: 1, 4: 1}

        resultado = resolver(
            clinicas=clinicas, pavimentos=pavimentos, alocacao_atual=atual
        )

        assert resultado.total_nao_alocado == 0
        assert resultado.pavimento_da_clinica(1) == 2
        assert resultado.pavimento_da_clinica(2) == 2
        assert resultado.pavimento_da_clinica(3) == 1
        assert resultado.pavimento_da_clinica(4) == 1
        assert resultado.clinicas_movidas == 0

    def test_alocacao_atual_nunca_gera_sobra_nem_sobrepoe_afinidade(self):
        # A estabilidade é a última prioridade: se a clínica preferida por
        # afinidade não é onde ela está hoje, a afinidade (nível 3) ainda
        # vence sobre a estabilidade (nível 6).
        clinica = Clinica(id=1, nome="Dermatologia", demanda=demanda_uniforme(4))
        pav_a = Pavimento(id=1, nome="A", capacidade=10)
        pav_b = Pavimento(id=2, nome="B", capacidade=10)

        resultado = resolver(
            clinicas=(clinica,),
            pavimentos=(pav_a, pav_b),
            afinidade={(1, pav_b.id): 1.0},
            alocacao_atual={1: pav_a.id},
        )

        assert resultado.pavimento_da_clinica(1) == pav_b.id
        assert resultado.total_nao_alocado == 0

    def test_clinica_obrigatoria_ignora_alocacao_atual_diferente(self):
        # A obrigatoriedade (nível 1) nunca cede — nem para a estabilidade.
        clinica = Clinica(id=1, nome="Presa", demanda=demanda_uniforme(5))
        pav_a = Pavimento(id=1, nome="A", capacidade=10)
        pav_b = Pavimento(id=2, nome="B", capacidade=10)

        resultado = resolver(
            clinicas=(clinica,),
            pavimentos=(pav_a, pav_b),
            obrigatorias={1: pav_a.id},
            alocacao_atual={1: pav_b.id},
        )

        assert resultado.pavimento_da_clinica(1) == pav_a.id

    def test_alocacao_atual_referenciando_pavimento_inexistente_e_ignorada(self):
        # Defensivo: se o mapa trouxer um pavimento que não existe mais na
        # entrada, o motor não pode quebrar — trata como "sem preferência".
        clinica = Clinica(id=1, nome="C1", demanda=demanda_uniforme(4))
        pavimento = Pavimento(id=1, nome="P1", capacidade=10)

        resultado = resolver(
            clinicas=(clinica,),
            pavimentos=(pavimento,),
            alocacao_atual={1: 999},
        )

        assert resultado.pavimento_da_clinica(1) == 1
        assert resultado.total_nao_alocado == 0

    def test_resultado_e_deterministico_com_alocacao_atual(self):
        clinicas = tuple(
            Clinica(id=i, nome=f"C{i}", demanda=demanda_uniforme(5))
            for i in range(1, 5)
        )
        pavimentos = (
            Pavimento(id=1, nome="P1", capacidade=10),
            Pavimento(id=2, nome="P2", capacidade=10),
        )
        atual = {1: 2, 2: 2, 3: 1, 4: 1}

        primeira = resolver(clinicas=clinicas, pavimentos=pavimentos, alocacao_atual=atual)
        segunda = resolver(clinicas=clinicas, pavimentos=pavimentos, alocacao_atual=atual)

        assert primeira == segunda


# ---------------------------------------------------------------------------
# Invariantes gerais
# ---------------------------------------------------------------------------


class TestInvariantes:

    @staticmethod
    def _cenario():
        clinicas = (
            Clinica(id=1, nome="Manhã pesada", demanda=demanda_em(MANHAS, 12)),
            Clinica(id=2, nome="Tarde pesada", demanda=demanda_em(TARDES, 11)),
            Clinica(id=3, nome="Uniforme", demanda=demanda_uniforme(6)),
            Clinica(id=4, nome="Pequena", demanda=demanda_uniforme(2)),
            Clinica(id=5, nome="Irregular", demanda=(3, 9, 0, 4, 7, 1, 8, 2, 5, 6)),
        )
        pavimentos = (
            Pavimento(id=1, nome="Térreo", capacidade=14),
            Pavimento(id=2, nome="1º andar", capacidade=12),
            Pavimento(id=3, nome="2º andar", capacidade=9),
        )
        return clinicas, pavimentos

    def test_toda_clinica_recebe_exatamente_um_pavimento(self):
        clinicas, pavimentos = self._cenario()
        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert len(resultado.por_clinica) == len(clinicas)
        assert {r.clinica_id for r in resultado.por_clinica} == {c.id for c in clinicas}

    def test_alocado_mais_nao_alocado_e_igual_a_demanda(self):
        clinicas, pavimentos = self._cenario()
        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)
        por_id = {c.id: c for c in clinicas}

        for r in resultado.por_clinica:
            demanda = por_id[r.clinica_id].demanda
            for t in range(NUM_TURNOS):
                assert r.alocado[t] + r.nao_alocado[t] == demanda[t]
                assert r.alocado[t] >= 0
                assert r.nao_alocado[t] >= 0

    def test_nenhum_pavimento_passa_da_capacidade(self):
        clinicas, pavimentos = self._cenario()
        resultado = resolver(clinicas=clinicas, pavimentos=pavimentos)

        for ocupacao in resultado.por_pavimento:
            for t in range(NUM_TURNOS):
                assert ocupacao.ocupacao[t] <= ocupacao.capacidade

    def test_resultado_e_deterministico(self):
        clinicas, pavimentos = self._cenario()
        primeira = resolver(clinicas=clinicas, pavimentos=pavimentos)
        segunda = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert primeira == segunda

    def test_indicadores_de_ocupacao(self):
        clinica = Clinica(id=1, nome="Meia carga", demanda=demanda_uniforme(5))
        pavimento = Pavimento(id=1, nome="P", capacidade=10)

        resultado = resolver(clinicas=(clinica,), pavimentos=(pavimento,))
        ocupacao = resultado.por_pavimento[0]

        assert ocupacao.ocupacao_media == pytest.approx(0.5)
        assert ocupacao.ocupacao_pico == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Validação de entrada
# ---------------------------------------------------------------------------


class TestValidacaoDeEntrada:

    def test_demanda_com_numero_errado_de_turnos(self):
        with pytest.raises(ValueError, match="turnos"):
            Clinica(id=1, nome="Torta", demanda=(1, 2, 3))

    def test_demanda_negativa(self):
        with pytest.raises(ValueError, match="negativa"):
            Clinica(id=1, nome="Negativa", demanda=(-1,) * NUM_TURNOS)

    def test_clinicas_com_id_repetido(self):
        c = Clinica(id=1, nome="A", demanda=demanda_uniforme(1))
        d = Clinica(id=1, nome="B", demanda=demanda_uniforme(1))
        with pytest.raises(ValueError, match="id repetido"):
            EntradaAlocacao(clinicas=(c, d), pavimentos=(Pavimento(id=1, nome="P", capacidade=5),))

    def test_obrigatoriedade_para_pavimento_inexistente(self):
        c = Clinica(id=1, nome="A", demanda=demanda_uniforme(1))
        with pytest.raises(ValueError, match="pavimento inexistente"):
            EntradaAlocacao(
                clinicas=(c,),
                pavimentos=(Pavimento(id=1, nome="P", capacidade=5),),
                obrigatorias={1: 99},
            )

    def test_clinicas_sem_pavimento(self):
        c = Clinica(id=1, nome="A", demanda=demanda_uniforme(1))
        with pytest.raises(ValueError, match="nenhum pavimento"):
            EntradaAlocacao(clinicas=(c,), pavimentos=())

    def test_tipo_de_restricao_invalido(self):
        with pytest.raises(ValueError, match="tipo de restrição"):
            Restricao(clinica_id=1, pavimento_id=1, tipo="talvez")

    def test_tipos_de_restricao_validos(self):
        assert Restricao(clinica_id=1, pavimento_id=1, tipo=OBRIGATORIO).tipo == "obrigatorio"
        assert Restricao(clinica_id=1, pavimento_id=1, tipo=PREFERENCIAL).tipo == "preferencial"

    def test_cenario_vazio(self):
        resultado = resolver(clinicas=(), pavimentos=(Pavimento(id=1, nome="P", capacidade=5),))
        assert resultado.por_clinica == ()
        assert resultado.total_nao_alocado == 0


# ---------------------------------------------------------------------------
# Sala especializada — pools segregados (padrão x especializada)
# ---------------------------------------------------------------------------
#
# Regra de negócio (não uma preferência): uma clínica com
# `precisa_sala_especializada=True` SÓ pode ocupar o pool "especializada" de
# um pavimento — nunca o "padrao", mesmo que ele tenha espaço de sobra. E o
# inverso também vale: uma clínica comum nunca ocupa a especializada, mesmo
# que ela esteja vazia enquanto a padrão do mesmo andar estoura. É reserva
# rígida, não pool compartilhado.


class TestSalaEspecializada:

    def test_pool_da_clinica(self):
        comum = Clinica(id=1, nome="Comum", demanda=demanda_uniforme(1))
        especial = Clinica(
            id=2, nome="Especial", demanda=demanda_uniforme(1), precisa_sala_especializada=True
        )
        assert pool_da_clinica(comum) == "padrao"
        assert pool_da_clinica(especial) == "especializada"

    def test_capacidade_do_pool(self):
        pavimento = Pavimento(id=1, nome="P", capacidade=7, capacidade_especializada=3)
        assert capacidade_do_pool(pavimento, "padrao") == 7
        assert capacidade_do_pool(pavimento, "especializada") == 3

    def test_pavimento_sem_capacidade_especializada_tem_default_zero(self):
        # Retrocompatibilidade: `Pavimento(id=.., nome=.., capacidade=N)` sem
        # saber de sala especializada continua significando "N padrão, 0
        # especializadas" — comportamento anterior à feature preservado.
        pavimento = Pavimento(id=1, nome="P", capacidade=10)
        assert pavimento.capacidade_especializada == 0
        assert pavimento.capacidade_total == 10

    def test_capacidade_especializada_negativa_e_invalida(self):
        with pytest.raises(ValueError, match="negativa"):
            Pavimento(id=1, nome="P", capacidade=10, capacidade_especializada=-1)

    def test_clinica_especializada_nunca_usa_pool_padrao_mesmo_com_espaco(self):
        # Pavimento com padrão vazio (sobrando) e especializada pequena e
        # cheia. A clínica especializada NÃO pode "vazar" para o padrão livre.
        especial = Clinica(
            id=1,
            nome="Ressonância",
            demanda=demanda_uniforme(10),
            precisa_sala_especializada=True,
        )
        pavimento = Pavimento(id=1, nome="P", capacidade=50, capacidade_especializada=3)

        resultado = resolver(clinicas=(especial,), pavimentos=(pavimento,))

        # Só 3 estações especializadas existem; o resto vira sobra — mesmo
        # havendo 50 estações padrão livres no mesmo pavimento.
        assert resultado.total_alocado == 3 * NUM_TURNOS
        assert resultado.total_nao_alocado == (10 - 3) * NUM_TURNOS

    def test_clinica_comum_nunca_ocupa_especializada_mesmo_com_padrao_cheia(self):
        # Pavimento com padrão pequena e cheia e especializada grande e vazia.
        # A clínica comum NÃO pode "vazar" para a especializada livre.
        comum = Clinica(id=1, nome="Comum", demanda=demanda_uniforme(10))
        pavimento = Pavimento(id=1, nome="P", capacidade=3, capacidade_especializada=50)

        resultado = resolver(clinicas=(comum,), pavimentos=(pavimento,))

        assert resultado.total_alocado == 3 * NUM_TURNOS
        assert resultado.total_nao_alocado == (10 - 3) * NUM_TURNOS

    def test_pools_segregados_no_mesmo_pavimento_simultaneamente(self):
        # Uma clínica comum e uma especializada dividem o MESMO pavimento sem
        # nunca disputar a mesma vaga — cada uma só vê o seu pool.
        comum = Clinica(id=1, nome="Comum", demanda=demanda_uniforme(5))
        especial = Clinica(
            id=2, nome="Especial", demanda=demanda_uniforme(5), precisa_sala_especializada=True
        )
        pavimento = Pavimento(id=1, nome="P", capacidade=5, capacidade_especializada=5)

        resultado = resolver(clinicas=(comum, especial), pavimentos=(pavimento,))

        assert resultado.total_nao_alocado == 0
        por_id = {r.clinica_id: r for r in resultado.por_clinica}
        assert por_id[1].total_alocado == 5 * NUM_TURNOS
        assert por_id[2].total_alocado == 5 * NUM_TURNOS

    def test_obrigatoriedade_de_pavimento_gera_sobra_no_pool_especializado(self):
        # Obrigatoriedade força o pavimento; a exigência de especializada
        # ainda assim roteia para o pool certo e pode gerar sobra ali, mesmo
        # com o pool padrão do mesmo pavimento vazio — os dois níveis de
        # obrigatoriedade (pavimento + pool) se combinam sem um sobrepor o
        # outro.
        especial = Clinica(
            id=1,
            nome="Hemodiálise",
            demanda=demanda_uniforme(10),
            precisa_sala_especializada=True,
        )
        pavimento = Pavimento(id=1, nome="P", capacidade=100, capacidade_especializada=2)

        resultado = resolver(
            clinicas=(especial,),
            pavimentos=(pavimento,),
            obrigatorias={1: pavimento.id},
        )

        assert resultado.pavimento_da_clinica(1) == pavimento.id
        assert resultado.total_alocado == 2 * NUM_TURNOS
        assert resultado.total_nao_alocado == (10 - 2) * NUM_TURNOS

    def test_clinica_especializada_escolhe_pavimento_com_pool_especializado(self):
        # Colocação gulosa: entre dois pavimentos, só um tem capacidade
        # especializada — a clínica especializada precisa ir para ele, mesmo
        # que o outro tenha capacidade total (padrão) muito maior.
        especial = Clinica(
            id=1, nome="Especial", demanda=demanda_uniforme(4), precisa_sala_especializada=True
        )
        sem_especializada = Pavimento(id=1, nome="Sem especializada", capacidade=100)
        com_especializada = Pavimento(
            id=2, nome="Com especializada", capacidade=0, capacidade_especializada=10
        )

        resultado = resolver(
            clinicas=(especial,), pavimentos=(sem_especializada, com_especializada)
        )

        assert resultado.pavimento_da_clinica(1) == com_especializada.id
        assert resultado.total_nao_alocado == 0

    def test_determinismo_com_dois_pools(self):
        # Mesma entrada com clínicas dos dois pools → mesma saída sempre.
        clinicas = (
            Clinica(id=1, nome="Comum A", demanda=demanda_uniforme(4)),
            Clinica(
                id=2, nome="Especial A", demanda=demanda_uniforme(3),
                precisa_sala_especializada=True,
            ),
            Clinica(id=3, nome="Comum B", demanda=demanda_uniforme(6)),
            Clinica(
                id=4, nome="Especial B", demanda=demanda_uniforme(2),
                precisa_sala_especializada=True,
            ),
        )
        pavimentos = (
            Pavimento(id=1, nome="P1", capacidade=6, capacidade_especializada=3),
            Pavimento(id=2, nome="P2", capacidade=6, capacidade_especializada=3),
        )

        primeira = resolver(clinicas=clinicas, pavimentos=pavimentos)
        segunda = resolver(clinicas=clinicas, pavimentos=pavimentos)

        assert [r.pavimento_id for r in primeira.por_clinica] == [
            r.pavimento_id for r in segunda.por_clinica
        ]
        assert primeira.total_nao_alocado == segunda.total_nao_alocado
        assert primeira.desvio_proporcional_total == segunda.desvio_proporcional_total
