"""
heuristica.py — Implementação do motor de alocação em fases.

O problema é um empacotamento vetorial: cada clínica é um vetor de 10 demandas
(uma por turno) e cada pavimento é uma caixa cuja capacidade vale nos 10 turnos.
Alocar é encaixar cada clínica inteira numa caixa sem estourar nenhum turno.
Como a clínica fica no mesmo pavimento a semana toda, o segredo é juntar
clínicas que se completam — uma cheia de manhã com uma cheia de tarde ocupam
bem o mesmo pavimento.

Cinco blocos, conforme a seção 8 do SAA_Arquitetura.pdf:

  1. Ingredientes — vetores de demanda, capacidades, obrigatoriedade, afinidade
  2. Fila        — com preferência primeiro, depois sem; dentro de cada
                   grupo, pelo pico (da maior para a menor)
  3. Colocação   — gulosa: cabe inteira? maior afinidade : menor estouro
  4. Melhoria    — MOVE/SWAP enquanto o placar melhorar
  5. Repartição  — a sobra de cada turno dividida proporcionalmente

O caráter do algoritmo: a preferência é um puxão, nunca uma imposição. Só a
obrigatoriedade força — e é a única coisa capaz de gerar grade não alocada.

SALAS ESPECIALIZADAS (POOLS) — cada pavimento na verdade tem DUAS caixas
independentes: o pool "padrao" (estações padrao_1est/padrao_2est) e o pool
"especializada" (esp_1est/esp_2est). Uma clínica só entra no pool que lhe
corresponde (`Clinica.precisa_sala_especializada`, ver
`src.domain.entidades.pool_da_clinica`) — nunca no outro, mesmo que ele esteja
vazio. Isso é uma decisão de negócio, não um detalhe técnico: a especializada é
RESERVADA, não um pool compartilhado com sobra da padrão. Por isso `carga`
deixou de ser `dict[pavimento_id, vetor]` e passou a ser
`dict[pavimento_id, dict[pool, vetor]]` — cada pavimento carrega dois vetores
de 10 turnos, um por pool, que nunca se somam entre si em nenhum cálculo de
capacidade/estouro. O equilíbrio proporcional (níveis 4 e 5) também vira dois
sub-problemas sobrepostos na mesma malha de pavimentos: o desvio é calculado
separadamente em cada pool e depois combinado (soma para o nível 4, máximo
para o nível 5) — nunca misturando D_t ou C entre pools.
"""

from __future__ import annotations

import logging
from itertools import combinations
from typing import Iterable, Mapping, Sequence

from src.domain.alocacao.solver import (
    EntradaAlocacao,
    OcupacaoPavimento,
    ResultadoAlocacao,
    ResultadoClinica,
)
from src.domain.entidades import (
    NUM_TURNOS,
    Clinica,
    Pavimento,
    capacidade_do_pool,
    pool_da_clinica,
)

logger = logging.getLogger(__name__)


#: Teto de passadas de melhoria. A busca local converge muito antes disso; o
#: limite existe só para garantir terminação diante de um empate cíclico.
MAX_PASSADAS_MELHORIA = 50

#: Os dois pools de capacidade que existem dentro de cada pavimento. Nunca se
#: misturam: uma clínica do pool "padrao" nunca compete por espaço no pool
#: "especializada", e vice-versa (reserva rígida, não pool compartilhado).
POOLS: tuple[str, ...] = ("padrao", "especializada")


# ---------------------------------------------------------------------------
# Bloco 5 — Repartição proporcional da sobra
# ---------------------------------------------------------------------------


def repartir_turno(demandas: Sequence[int], capacidade: int) -> list[int]:
    """
    Distribui a capacidade de um turno entre as clínicas do pavimento.

    Se a demanda total cabe, cada clínica recebe tudo o que pediu. Se estoura,
    cada uma recebe ⌊demanda × capacidade / D⌋ e as vagas restantes vão para os
    maiores restos fracionários (método do maior resto). Assim nenhuma clínica
    se prejudica mais que as outras — todas mantêm aproximadamente a mesma
    fração da sua demanda.

    Exemplo (seção 8, validação com dados reais): duas clínicas pedindo 17 e 13
    estações num pavimento de 9 recebem 5 e 4 — ambas ~30% do que pediram.

    Esta função é agnóstica a pool — quem chama já filtrou `demandas` para as
    clínicas de um único pool e passa a capacidade daquele pool.
    """
    total = sum(demandas)
    if total <= capacidade:
        return list(demandas)

    base = [d * capacidade // total for d in demandas]
    restante = capacidade - sum(base)

    # Ordena por maior resto fracionário. O resto de (d × cap / D) é
    # (d × cap) % D — comparável entre si por terem o mesmo denominador.
    # Empates caem para a maior demanda e, por fim, para o índice (determinismo).
    ordem = sorted(
        range(len(demandas)),
        key=lambda i: (-((demandas[i] * capacidade) % total), -demandas[i], i),
    )
    for i in ordem[:restante]:
        base[i] += 1

    return base


# ---------------------------------------------------------------------------
# Auxiliares de carga e placar
# ---------------------------------------------------------------------------
#
# `carga[pavimento_id][pool]` é o vetor de 10 turnos ocupados naquele
# pavimento, naquele pool. Os dois pools de um mesmo pavimento são contas
# totalmente independentes — nunca se somam, nunca se emprestam capacidade.


def _carga_zerada(pavimentos: Iterable[Pavimento]) -> dict[int, dict[str, list[int]]]:
    return {p.id: {pool: [0] * NUM_TURNOS for pool in POOLS} for p in pavimentos}


def _somar(
    carga: dict[int, dict[str, list[int]]], pavimento_id: int, clinica: Clinica
) -> None:
    # Pool-aware: a clínica só pesa no vetor do SEU pool (padrão ou
    # especializada) naquele pavimento — nunca no outro.
    vetor = carga[pavimento_id][pool_da_clinica(clinica)]
    for t, q in enumerate(clinica.demanda):
        vetor[t] += q


def _subtrair(
    carga: dict[int, dict[str, list[int]]], pavimento_id: int, clinica: Clinica
) -> None:
    vetor = carga[pavimento_id][pool_da_clinica(clinica)]
    for t, q in enumerate(clinica.demanda):
        vetor[t] -= q


def _sobra_total(
    carga: Mapping[int, Mapping[str, list[int]]], pavimentos: Iterable[Pavimento]
) -> int:
    """
    Grades que não cabem — soma dos estouros de capacidade em todos os turnos.

    Pool-aware: soma o estouro do pool padrão (contra `p.capacidade`) MAIS o
    estouro do pool especializada (contra `p.capacidade_especializada`) — os
    dois sub-problemas de empacotamento sobrepostos na mesma malha de
    pavimentos, nunca misturados entre si.
    """
    pavimentos = list(pavimentos)
    return sum(
        max(0, carga[p.id][pool][t] - capacidade_do_pool(p, pool))
        for p in pavimentos
        for pool in POOLS
        for t in range(NUM_TURNOS)
    )


def _estouro_se_entrar(
    carga: Mapping[int, Mapping[str, list[int]]], pavimento: Pavimento, clinica: Clinica
) -> int:
    """Quanto de estouro a clínica causaria neste pavimento, sem contar o que já há."""
    pool = pool_da_clinica(clinica)
    capacidade = capacidade_do_pool(pavimento, pool)
    vetor = carga[pavimento.id][pool]
    return sum(
        max(0, vetor[t] + clinica.demanda[t] - capacidade)
        - max(0, vetor[t] - capacidade)
        for t in range(NUM_TURNOS)
    )


def _cabe_inteira(
    carga: Mapping[int, Mapping[str, list[int]]], pavimento: Pavimento, clinica: Clinica
) -> bool:
    """A clínica cabe em TODO turno, sem estourar a capacidade do SEU pool?"""
    pool = pool_da_clinica(clinica)
    capacidade = capacidade_do_pool(pavimento, pool)
    vetor = carga[pavimento.id][pool]
    return all(vetor[t] + clinica.demanda[t] <= capacidade for t in range(NUM_TURNOS))


def _folga_residual(
    carga: Mapping[int, Mapping[str, list[int]]], pavimento: Pavimento, clinica: Clinica
) -> int:
    """
    Capacidade que sobraria no pavimento (no pool da clínica) depois de
    acomodá-la.

    Não é mais o desempate PRINCIPAL da colocação gulosa (ver
    `_desvio_proporcional_pavimento`) porque "sempre apertar o mesmo pavimento
    até estourar antes de abrir outro" é exatamente o padrão que concentrava a
    ocupação em poucos pavimentos (diagnóstico da Fase 1). Mantido como
    desempate de última instância (antes do id) para os raríssimos casos em
    que afinidade E desvio proporcional empatam exatamente.
    """
    pool = pool_da_clinica(clinica)
    capacidade = capacidade_do_pool(pavimento, pool)
    vetor = carga[pavimento.id][pool]
    return sum(capacidade - vetor[t] - clinica.demanda[t] for t in range(NUM_TURNOS))


# ---------------------------------------------------------------------------
# Equilíbrio proporcional (níveis 4 e 5 da hierarquia de objetivos)
# ---------------------------------------------------------------------------
#
# Carga-alvo proporcional: alvo_p,t = D_t · c_p / C, onde D_t é a demanda total
# do turno t (todas as clínicas DO MESMO POOL), c_p a capacidade do pavimento p
# NAQUELE POOL e C a soma das capacidades dos pavimentos ATIVOS naquele pool
# (capacidade do pool > 0). Pavimentos de capacidade 0 num pool nunca recebem
# clínica naquele pool (comportamento preservado, agora por pool) e ficam fora
# de C e de qualquer cálculo de taxa daquele pool — mas continuam entrando no
# somatório de desvio abaixo (defensivamente: se por algum motivo tiverem
# carga, isso pesa contra a solução em vez de ser ignorado).
#
# Para evitar divisão (e o problema de c_p = 0 no denominador de uma "taxa"),
# comparamos o desvio na forma sem fração: |L_p,t · C - D_t · c_p|. Isso é
# equivalente, a menos de fator comum C > 0, a comparar |L_p,t/c_p - D_t/C|
# quando c_p > 0, e evita qualquer divisão por zero.
#
# Os dois pools (padrão e especializada) são dois sub-problemas de equilíbrio
# INDEPENDENTES sobrepostos na mesma malha de pavimentos: D_t, c_p e C do pool
# padrão nunca se misturam com os do pool especializada. Por isso as funções
# abaixo recebem `demanda_total_turno_por_pool`/`capacidade_ativa_total_por_pool`
# — dicionários com uma entrada por pool — em vez de um único valor.


def _demanda_total_por_turno_por_pool(clinicas: Iterable[Clinica]) -> dict[str, list[int]]:
    """D_t de cada pool — demanda das clínicas DAQUELE pool, somada por turno."""
    totais = {pool: [0] * NUM_TURNOS for pool in POOLS}
    for clinica in clinicas:
        vetor = totais[pool_da_clinica(clinica)]
        for t, q in enumerate(clinica.demanda):
            vetor[t] += q
    return totais


def _capacidade_ativa_total_por_pool(pavimentos: Iterable[Pavimento]) -> dict[str, int]:
    """C de cada pool — soma das capacidades dos pavimentos ativos NAQUELE pool."""
    pavimentos = list(pavimentos)
    return {
        pool: sum(
            capacidade_do_pool(p, pool) for p in pavimentos if capacidade_do_pool(p, pool) > 0
        )
        for pool in POOLS
    }


def _desvio_proporcional_pavimento(
    carga: Mapping[int, Mapping[str, list[int]]],
    pavimento: Pavimento,
    clinica: Clinica,
    demanda_total_turno_por_pool: Mapping[str, Sequence[int]],
    capacidade_ativa_total_por_pool: Mapping[str, int],
) -> int:
    """
    Quanto o pavimento se desviaria da carga-alvo proporcional (no pool da
    clínica) se ela entrasse agora — Σ_t |L_p,t·C - D_t·c_p| considerando só
    este pavimento e o pool ao qual a clínica pertence.

    Usado como desempate PRINCIPAL da colocação gulosa: entre pavimentos onde
    a clínica cabe inteira e com a mesma afinidade, escolhe o que fica mais
    perto do seu alvo proporcional em vez do que sobra menos espaço (que
    concentraria tudo num pavimento só até ele estourar).
    """
    pool = pool_da_clinica(clinica)
    capacidade_ativa_total = capacidade_ativa_total_por_pool[pool]
    if capacidade_ativa_total == 0:
        return 0
    demanda_total_turno = demanda_total_turno_por_pool[pool]
    capacidade_pavimento = capacidade_do_pool(pavimento, pool)
    vetor = carga[pavimento.id][pool]
    total = 0
    for t in range(NUM_TURNOS):
        carga_t = vetor[t] + clinica.demanda[t]
        total += abs(
            carga_t * capacidade_ativa_total - demanda_total_turno[t] * capacidade_pavimento
        )
    return total


def _desvio_proporcional_total(
    carga: Mapping[int, Mapping[str, list[int]]],
    pavimentos: Iterable[Pavimento],
    demanda_total_turno_por_pool: Mapping[str, Sequence[int]],
    capacidade_ativa_total_por_pool: Mapping[str, int],
) -> int:
    """
    Nível 4 do placar: Σ_{p,t} |L_p,t·C - D_t·c_p| na solução inteira — somado
    nos dois pools (padrão e especializada são sub-problemas independentes que
    se somam para compor o desvio agregado total).
    """
    pavimentos = list(pavimentos)
    total = 0
    for pool in POOLS:
        capacidade_ativa_total = capacidade_ativa_total_por_pool[pool]
        if capacidade_ativa_total == 0:
            continue
        demanda_total_turno = demanda_total_turno_por_pool[pool]
        for p in pavimentos:
            vetor = carga[p.id][pool]
            capacidade_pavimento = capacidade_do_pool(p, pool)
            for t in range(NUM_TURNOS):
                total += abs(
                    vetor[t] * capacidade_ativa_total
                    - demanda_total_turno[t] * capacidade_pavimento
                )
    return total


def _pior_desequilibrio_pontual(
    carga: Mapping[int, Mapping[str, list[int]]],
    pavimentos: Iterable[Pavimento],
    demanda_total_turno_por_pool: Mapping[str, Sequence[int]],
    capacidade_ativa_total_por_pool: Mapping[str, int],
) -> int:
    """
    Nível 5 do placar: maior |L_p,t·C - D_t·c_p| isolado entre todos os pares
    pavimento/turno, OLHANDO OS DOIS POOLS — o pior de todos, seja ele no
    padrão ou na especializada. Desempata DEPOIS do agregado (nível 4): duas
    soluções com a mesma soma de desvio podem ter um pico muito pior num único
    turno/pool, e essa é a que preterimos.
    """
    pavimentos = list(pavimentos)
    pior = 0
    for pool in POOLS:
        capacidade_ativa_total = capacidade_ativa_total_por_pool[pool]
        if capacidade_ativa_total == 0:
            continue
        demanda_total_turno = demanda_total_turno_por_pool[pool]
        for p in pavimentos:
            vetor = carga[p.id][pool]
            capacidade_pavimento = capacidade_do_pool(p, pool)
            for t in range(NUM_TURNOS):
                desvio = abs(
                    vetor[t] * capacidade_ativa_total
                    - demanda_total_turno[t] * capacidade_pavimento
                )
                if desvio > pior:
                    pior = desvio
    return pior


def _clinicas_movidas(
    atribuicao: Mapping[int, int], alocacao_atual: Mapping[int, int]
) -> int:
    """
    Nível 6 do placar: nº de clínicas cujo pavimento na solução atual difere
    de `alocacao_atual` (execução anterior OU ajuste manual — tratados de
    forma uniforme, sem distinção). É preferência de estabilidade, a de MENOR
    prioridade da hierarquia: só desempata depois de sobra, afinidade e
    equilíbrio proporcional (níveis 2 a 5) já estarem decididos.

    Não depende de pool — a clínica é a mesma clínica, movida ou não.
    """
    return sum(
        1
        for clinica_id, pavimento_id in alocacao_atual.items()
        if clinica_id in atribuicao and atribuicao[clinica_id] != pavimento_id
    )


# ---------------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------------


class SolverHeuristico:
    """
    Colocação gulosa seguida de busca local por MOVE/SWAP.

    Satisfaz o protocolo `SolverAlocacao`. O problema real é pequeno
    (43 clínicas × 9 pavimentos) e a heurística zerou a sobra nos dados do HC;
    se um dia for preciso o ótimo garantido, basta plugar outro solver.
    """

    def resolver(self, entrada: EntradaAlocacao) -> ResultadoAlocacao:
        clinicas = entrada.clinicas
        pavimentos = entrada.pavimentos

        if not clinicas:
            return ResultadoAlocacao(
                por_clinica=(),
                por_pavimento=tuple(
                    OcupacaoPavimento(
                        pavimento_id=p.id,
                        nome=p.nome,
                        capacidade=p.capacidade_total,
                        ocupacao=(0,) * NUM_TURNOS,
                        demanda=(0,) * NUM_TURNOS,
                    )
                    for p in pavimentos
                ),
            )

        logger.info(
            "Motor iniciado: %d clínicas | %d pavimentos | %d obrigatoriedades",
            len(clinicas),
            len(pavimentos),
            len(entrada.obrigatorias),
        )

        atribuicao = self._colocacao_gulosa(entrada)
        atribuicao = self._passada_de_melhoria(entrada, atribuicao)
        resultado = self._montar_resultado(entrada, atribuicao)

        logger.info(
            "Motor finalizado: %d grades alocadas | %d não alocadas",
            resultado.total_alocado,
            resultado.total_nao_alocado,
        )
        return resultado

    # -- Blocos 1 a 3: ingredientes, fila e colocação -----------------------

    def _colocacao_gulosa(self, entrada: EntradaAlocacao) -> dict[int, int]:
        carga = _carga_zerada(entrada.pavimentos)
        atribuicao: dict[int, int] = {}

        por_id = {c.id: c for c in entrada.clinicas}

        # D_t e C, por pool, para o desempate proporcional (nível 4/5) já na
        # colocação inicial — evita que a gulosa concentre e deixe tudo para a
        # melhoria desfazer depois.
        demanda_total_turno_por_pool = _demanda_total_por_turno_por_pool(entrada.clinicas)
        capacidade_ativa_total_por_pool = _capacidade_ativa_total_por_pool(entrada.pavimentos)

        # Bloco 1 — as obrigatórias vão direto ao seu pavimento e travam.
        # Elas entram antes de todo mundo, mesmo que estourem a capacidade.
        # `_somar` já é pool-aware: uma obrigatória com
        # `precisa_sala_especializada=True` pesa no pool especializada do
        # pavimento forçado, e pode gerar sobra ali se ele não tiver
        # especializada suficiente — exatamente como uma obrigatoriedade comum
        # gera sobra no pool padrão.
        for clinica_id, pavimento_id in entrada.obrigatorias.items():
            clinica = por_id[clinica_id]
            atribuicao[clinica_id] = pavimento_id
            _somar(carga, pavimento_id, clinica)
            logger.debug(
                "obrigatória: %s → pavimento %d", clinica.nome, pavimento_id
            )

        # Bloco 2 — fila das livres: primeiro quem tem preferência declarada,
        # depois quem não tem. Preferência já vence equilíbrio proporcional na
        # hierarquia de objetivos (nível 3 > nível 4), então deixamos essas
        # clínicas reservarem espaço no pavimento preferido antes que uma
        # clínica sem preferência o preencha só por conveniência de encaixe.
        # Dentro de cada grupo, mantém o critério de empacotamento original —
        # pico decrescente, depois total, depois id — para não abrir mão da
        # minimização de sobra (nível 2, que continua acima de preferência).
        # A exigência de sala especializada não entra na ordenação da fila —
        # ela decide ONDE a clínica pode caber (via `_cabe_inteira` pool-aware
        # abaixo), não a ordem em que é atendida.
        clinicas_com_preferencia = {
            clinica_id for clinica_id, _pavimento_id in entrada.afinidade
        }
        livres = [c for c in entrada.clinicas if c.id not in entrada.obrigatorias]
        com_preferencia = [c for c in livres if c.id in clinicas_com_preferencia]
        sem_preferencia = [c for c in livres if c.id not in clinicas_com_preferencia]
        ordenar = lambda grupo: sorted(grupo, key=lambda c: (-c.pico, -c.total, c.id))
        fila = ordenar(com_preferencia) + ordenar(sem_preferencia)

        # Bloco 3 — colocação gulosa.
        for clinica in fila:
            # `_cabe_inteira` já é pool-aware: só considera candidato um
            # pavimento com espaço no pool DA CLÍNICA — uma clínica comum
            # nunca vê a especializada como candidata, mesmo que a padrão do
            # andar esteja cheia (reserva rígida, não pool compartilhado).
            candidatos = [
                p for p in entrada.pavimentos if _cabe_inteira(carga, p, clinica)
            ]

            if candidatos:
                # Cabe inteira em algum lugar: manda para o de maior afinidade
                # (nível 3). Empate → o que fica mais perto do seu alvo
                # proporcional (níveis 4/5), não o que sobra menos espaço —
                # senão a gulosa empurra sempre para o mesmo pavimento até
                # estourar antes de considerar outro (causa raiz do
                # desequilíbrio diagnosticada na Fase 1). Último desempate:
                # folga residual e, por fim, id (determinismo).
                escolhido = min(
                    candidatos,
                    key=lambda p: (
                        -self._afinidade(entrada, clinica.id, p.id),
                        _desvio_proporcional_pavimento(
                            carga,
                            p,
                            clinica,
                            demanda_total_turno_por_pool,
                            capacidade_ativa_total_por_pool,
                        ),
                        _folga_residual(carga, p, clinica),
                        p.id,
                    ),
                )
            else:
                # Não cabe em lugar nenhum (no pool da clínica): escolhe o de
                # menor estouro NAQUELE pool. Empate → maior afinidade. Uma
                # clínica que exige especializada só compara estouro entre os
                # pools especializados dos pavimentos — nunca considera o pool
                # padrão como alternativa, mesmo que ele tenha espaço livre.
                escolhido = min(
                    entrada.pavimentos,
                    key=lambda p: (
                        _estouro_se_entrar(carga, p, clinica),
                        -self._afinidade(entrada, clinica.id, p.id),
                        p.id,
                    ),
                )
                logger.debug(
                    "%s não cabe inteira em nenhum pavimento (pool %s); menor estouro é %s",
                    clinica.nome,
                    pool_da_clinica(clinica),
                    escolhido.nome,
                )

            atribuicao[clinica.id] = escolhido.id
            _somar(carga, escolhido.id, clinica)

        return atribuicao

    # -- Bloco 4: passada de melhoria --------------------------------------

    def _passada_de_melhoria(
        self, entrada: EntradaAlocacao, atribuicao: dict[int, int]
    ) -> dict[int, int]:
        """
        Busca local: aplica MOVE e SWAP enquanto o placar melhorar.

        Placar lexicográfico — cada nível só desempata quando todos os
        anteriores empatam (tupla comparada em ordem, nunca soma de pesos):

          nível 2 — sobra total (obrigatoriedades já fixaram o nível 1),
                     somada nos dois pools
          nível 3 — afinidade total, negada (mais afinidade = "menor")
          nível 4 — desvio proporcional agregado Σ|L·C - D·c|, somado nos
                     dois pools
          nível 5 — pior desequilíbrio pontual (maior desvio isolado entre os
                     dois pools)
          nível 6 — nº de clínicas movidas em relação a `alocacao_atual`
          nível 7 — desempate por id: não entra no placar; é garantido pela
                     ordem determinística de iteração de `moveis`/`pavimentos`.

        Clínicas obrigatórias nunca se movem. MOVE e SWAP continuam livres
        para levar uma clínica a QUALQUER pavimento — `_somar`/`_subtrair`
        são pool-aware e cuidam sozinhas de mexer no vetor certo; o placar
        (via `_sobra_total` etc., também pool-aware) rejeita qualquer solução
        que jogue uma clínica especializada num pool padrão isolado ou
        vice-versa, porque isso não muda o pool em que ela é contada — o pool
        é decidido pela clínica, não pelo pavimento escolhido.
        """
        por_id = {c.id: c for c in entrada.clinicas}
        moveis = [c for c in entrada.clinicas if c.id not in entrada.obrigatorias]
        if not moveis or len(entrada.pavimentos) < 2:
            return atribuicao

        carga = _carga_zerada(entrada.pavimentos)
        for clinica_id, pavimento_id in atribuicao.items():
            _somar(carga, pavimento_id, por_id[clinica_id])

        demanda_total_turno_por_pool = _demanda_total_por_turno_por_pool(entrada.clinicas)
        capacidade_ativa_total_por_pool = _capacidade_ativa_total_por_pool(entrada.pavimentos)

        def placar() -> tuple[int, float, int, int, int]:
            return (
                _sobra_total(carga, entrada.pavimentos),
                -self._afinidade_total(entrada, atribuicao),
                _desvio_proporcional_total(
                    carga,
                    entrada.pavimentos,
                    demanda_total_turno_por_pool,
                    capacidade_ativa_total_por_pool,
                ),
                _pior_desequilibrio_pontual(
                    carga,
                    entrada.pavimentos,
                    demanda_total_turno_por_pool,
                    capacidade_ativa_total_por_pool,
                ),
                _clinicas_movidas(atribuicao, entrada.alocacao_atual),
            )

        atual = placar()

        for passada in range(MAX_PASSADAS_MELHORIA):
            melhorou = False

            # MOVE — tirar uma clínica do seu pavimento e pôr em outro.
            for clinica in moveis:
                origem = atribuicao[clinica.id]
                for pavimento in entrada.pavimentos:
                    if pavimento.id == origem:
                        continue

                    _subtrair(carga, origem, clinica)
                    _somar(carga, pavimento.id, clinica)
                    atribuicao[clinica.id] = pavimento.id

                    candidato = placar()
                    if candidato < atual:
                        atual = candidato
                        melhorou = True
                        origem = pavimento.id  # a clínica agora mora aqui
                    else:
                        _subtrair(carga, pavimento.id, clinica)
                        _somar(carga, origem, clinica)
                        atribuicao[clinica.id] = origem

            # SWAP — trocar duas clínicas de pavimento.
            for clinica_a, clinica_b in combinations(moveis, 2):
                pav_a = atribuicao[clinica_a.id]
                pav_b = atribuicao[clinica_b.id]
                if pav_a == pav_b:
                    continue

                _subtrair(carga, pav_a, clinica_a)
                _subtrair(carga, pav_b, clinica_b)
                _somar(carga, pav_b, clinica_a)
                _somar(carga, pav_a, clinica_b)
                atribuicao[clinica_a.id] = pav_b
                atribuicao[clinica_b.id] = pav_a

                candidato = placar()
                if candidato < atual:
                    atual = candidato
                    melhorou = True
                else:
                    _subtrair(carga, pav_b, clinica_a)
                    _subtrair(carga, pav_a, clinica_b)
                    _somar(carga, pav_a, clinica_a)
                    _somar(carga, pav_b, clinica_b)
                    atribuicao[clinica_a.id] = pav_a
                    atribuicao[clinica_b.id] = pav_b

            if not melhorou:
                logger.debug("melhoria convergiu na passada %d", passada + 1)
                break
        else:
            logger.warning(
                "melhoria atingiu o teto de %d passadas sem convergir",
                MAX_PASSADAS_MELHORIA,
            )

        return atribuicao

    # -- Bloco 5: repartição e montagem do resultado ------------------------

    def _montar_resultado(
        self, entrada: EntradaAlocacao, atribuicao: Mapping[int, int]
    ) -> ResultadoAlocacao:
        por_clinica: list[ResultadoClinica] = []
        por_pavimento: list[OcupacaoPavimento] = []

        # Indicadores dos níveis 4, 5 e 6 na solução final — calculados sobre a
        # mesma carga final que gera `por_pavimento`, para relatar ao chamador
        # (serviço/tela) o quão equilibrada e estável a solução ficou.
        por_id = {c.id: c for c in entrada.clinicas}
        carga_final = _carga_zerada(entrada.pavimentos)
        for clinica_id, pavimento_id in atribuicao.items():
            _somar(carga_final, pavimento_id, por_id[clinica_id])
        demanda_total_turno_por_pool = _demanda_total_por_turno_por_pool(entrada.clinicas)
        capacidade_ativa_total_por_pool = _capacidade_ativa_total_por_pool(entrada.pavimentos)
        desvio_proporcional_total = _desvio_proporcional_total(
            carga_final,
            entrada.pavimentos,
            demanda_total_turno_por_pool,
            capacidade_ativa_total_por_pool,
        )
        pior_desequilibrio_pontual = _pior_desequilibrio_pontual(
            carga_final,
            entrada.pavimentos,
            demanda_total_turno_por_pool,
            capacidade_ativa_total_por_pool,
        )
        clinicas_movidas = _clinicas_movidas(atribuicao, entrada.alocacao_atual)

        for pavimento in entrada.pavimentos:
            ocupantes = [
                c for c in entrada.clinicas if atribuicao[c.id] == pavimento.id
            ]
            # Separa os ocupantes do pavimento pelo SEU pool — a repartição
            # proporcional da sobra (bloco 5) roda uma vez por pool, cada uma
            # só contra a capacidade daquele pool. Uma clínica especializada
            # nunca disputa espaço com uma padrão nesta conta, mesmo estando
            # no mesmo pavimento.
            ocupantes_por_pool = {
                pool: [c for c in ocupantes if pool_da_clinica(c) == pool]
                for pool in POOLS
            }

            alocado_por_clinica: dict[int, list[int]] = {
                c.id: [0] * NUM_TURNOS for c in ocupantes
            }
            ocupacao = [0] * NUM_TURNOS
            demanda = [0] * NUM_TURNOS

            for pool in POOLS:
                grupo = ocupantes_por_pool[pool]
                capacidade_pool = capacidade_do_pool(pavimento, pool)
                for t in range(NUM_TURNOS):
                    demandas_do_turno = [c.demanda[t] for c in grupo]
                    recebido = repartir_turno(demandas_do_turno, capacidade_pool)

                    for clinica, quantidade in zip(grupo, recebido):
                        alocado_por_clinica[clinica.id][t] = quantidade

                    # ocupacao/demanda do pavimento são o agregado dos dois
                    # pools — o que a tela e os relatórios de "ocupação do
                    # pavimento inteiro" esperam.
                    ocupacao[t] += sum(recebido)
                    demanda[t] += sum(demandas_do_turno)

            for clinica in ocupantes:
                alocado = alocado_por_clinica[clinica.id]
                por_clinica.append(
                    ResultadoClinica(
                        clinica_id=clinica.id,
                        nome=clinica.nome,
                        pavimento_id=pavimento.id,
                        alocado=tuple(alocado),
                        nao_alocado=tuple(
                            clinica.demanda[t] - alocado[t] for t in range(NUM_TURNOS)
                        ),
                    )
                )

            por_pavimento.append(
                OcupacaoPavimento(
                    pavimento_id=pavimento.id,
                    nome=pavimento.nome,
                    # Capacidade COMBINADA (padrão + especializada): ocupacao/
                    # demanda acima já somam os dois pools, então o campo de
                    # capacidade que os acompanha também precisa ser o total —
                    # senão `ocupacao_media`/`ocupacao_pico` (solver.py)
                    # comparariam ocupação de dois pools contra a capacidade
                    # de um só.
                    capacidade=pavimento.capacidade_total,
                    ocupacao=tuple(ocupacao),
                    demanda=tuple(demanda),
                )
            )

        # Mantém a ordem original das clínicas na saída — mais previsível para
        # quem consome (testes, telas e serviços).
        ordem = {c.id: i for i, c in enumerate(entrada.clinicas)}
        por_clinica.sort(key=lambda r: ordem[r.clinica_id])

        return ResultadoAlocacao(
            por_clinica=tuple(por_clinica),
            por_pavimento=tuple(por_pavimento),
            desvio_proporcional_total=desvio_proporcional_total,
            pior_desequilibrio_pontual=pior_desequilibrio_pontual,
            clinicas_movidas=clinicas_movidas,
        )

    # -- Afinidade ---------------------------------------------------------

    @staticmethod
    def _afinidade(entrada: EntradaAlocacao, clinica_id: int, pavimento_id: int) -> float:
        return entrada.afinidade.get((clinica_id, pavimento_id), 0.0)

    @staticmethod
    def _afinidade_total(
        entrada: EntradaAlocacao, atribuicao: Mapping[int, int]
    ) -> float:
        return sum(
            entrada.afinidade.get((clinica_id, pavimento_id), 0.0)
            for clinica_id, pavimento_id in atribuicao.items()
        )
