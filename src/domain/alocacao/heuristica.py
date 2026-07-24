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
  2. Fila        — clínicas ordenadas pelo pico, da maior para a menor
  3. Colocação   — gulosa: cabe inteira? maior afinidade : menor estouro
  4. Melhoria    — MOVE/SWAP enquanto o placar melhorar
  5. Repartição  — a sobra de cada turno dividida proporcionalmente

O caráter do algoritmo: a preferência é um puxão, nunca uma imposição. Só a
obrigatoriedade força — e é a única coisa capaz de gerar grade não alocada.
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
from src.domain.entidades import NUM_TURNOS, Clinica, Pavimento

logger = logging.getLogger(__name__)


#: Teto de passadas de melhoria. A busca local converge muito antes disso; o
#: limite existe só para garantir terminação diante de um empate cíclico.
MAX_PASSADAS_MELHORIA = 50


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


def _carga_zerada(pavimentos: Iterable[Pavimento]) -> dict[int, list[int]]:
    return {p.id: [0] * NUM_TURNOS for p in pavimentos}


def _somar(carga: dict[int, list[int]], pavimento_id: int, clinica: Clinica) -> None:
    vetor = carga[pavimento_id]
    for t, q in enumerate(clinica.demanda):
        vetor[t] += q


def _subtrair(carga: dict[int, list[int]], pavimento_id: int, clinica: Clinica) -> None:
    vetor = carga[pavimento_id]
    for t, q in enumerate(clinica.demanda):
        vetor[t] -= q


def _sobra_total(carga: Mapping[int, list[int]], pavimentos: Iterable[Pavimento]) -> int:
    """Grades que não cabem — soma dos estouros de capacidade em todos os turnos."""
    return sum(
        max(0, carga[p.id][t] - p.capacidade)
        for p in pavimentos
        for t in range(NUM_TURNOS)
    )


def _estouro_se_entrar(
    carga: Mapping[int, list[int]], pavimento: Pavimento, clinica: Clinica
) -> int:
    """Quanto de estouro a clínica causaria neste pavimento, sem contar o que já há."""
    vetor = carga[pavimento.id]
    return sum(
        max(0, vetor[t] + clinica.demanda[t] - pavimento.capacidade)
        - max(0, vetor[t] - pavimento.capacidade)
        for t in range(NUM_TURNOS)
    )


def _cabe_inteira(
    carga: Mapping[int, list[int]], pavimento: Pavimento, clinica: Clinica
) -> bool:
    """A clínica cabe em TODO turno, sem estourar a capacidade?"""
    vetor = carga[pavimento.id]
    return all(
        vetor[t] + clinica.demanda[t] <= pavimento.capacidade
        for t in range(NUM_TURNOS)
    )


def _folga_residual(
    carga: Mapping[int, list[int]], pavimento: Pavimento, clinica: Clinica
) -> int:
    """
    Capacidade que sobraria no pavimento depois de acomodar a clínica.

    Menor folga = encaixe mais justo. Serve de desempate quando duas opções têm
    a mesma afinidade: preferimos apertar um pavimento e deixar outro livre para
    uma clínica grande que ainda virá.
    """
    vetor = carga[pavimento.id]
    return sum(
        pavimento.capacidade - vetor[t] - clinica.demanda[t]
        for t in range(NUM_TURNOS)
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
                        capacidade=p.capacidade,
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

        # Bloco 1 — as obrigatórias vão direto ao seu pavimento e travam.
        # Elas entram antes de todo mundo, mesmo que estourem a capacidade.
        for clinica_id, pavimento_id in entrada.obrigatorias.items():
            clinica = por_id[clinica_id]
            atribuicao[clinica_id] = pavimento_id
            _somar(carga, pavimento_id, clinica)
            logger.debug(
                "obrigatória: %s → pavimento %d", clinica.nome, pavimento_id
            )

        # Bloco 2 — fila das livres por pico, do maior para o menor.
        # Quem tem o turno mais cheio escolhe primeiro, porque é quem tem menos
        # opções de encaixe. Empates caem para a demanda total e depois para o
        # id, garantindo que a mesma entrada produza sempre a mesma saída.
        livres = [c for c in entrada.clinicas if c.id not in entrada.obrigatorias]
        fila = sorted(livres, key=lambda c: (-c.pico, -c.total, c.id))

        # Bloco 3 — colocação gulosa.
        for clinica in fila:
            candidatos = [
                p for p in entrada.pavimentos if _cabe_inteira(carga, p, clinica)
            ]

            if candidatos:
                # Cabe inteira em algum lugar: manda para o de maior afinidade.
                # Empate → encaixe mais justo (menor folga residual).
                escolhido = min(
                    candidatos,
                    key=lambda p: (
                        -self._afinidade(entrada, clinica.id, p.id),
                        _folga_residual(carga, p, clinica),
                        p.id,
                    ),
                )
            else:
                # Não cabe em lugar nenhum: escolhe o de menor estouro.
                # Empate → maior afinidade.
                escolhido = min(
                    entrada.pavimentos,
                    key=lambda p: (
                        _estouro_se_entrar(carga, p, clinica),
                        -self._afinidade(entrada, clinica.id, p.id),
                        p.id,
                    ),
                )
                logger.debug(
                    "%s não cabe inteira em nenhum pavimento; menor estouro é %s",
                    clinica.nome,
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

        Placar lexicográfico: 1º menos sobra, 2º mais afinidade. Clínicas
        obrigatórias nunca se movem.
        """
        por_id = {c.id: c for c in entrada.clinicas}
        moveis = [c for c in entrada.clinicas if c.id not in entrada.obrigatorias]
        if not moveis or len(entrada.pavimentos) < 2:
            return atribuicao

        carga = _carga_zerada(entrada.pavimentos)
        for clinica_id, pavimento_id in atribuicao.items():
            _somar(carga, pavimento_id, por_id[clinica_id])

        def placar() -> tuple[int, float]:
            # Minimizamos a tupla: sobra primeiro, afinidade negada depois.
            return (
                _sobra_total(carga, entrada.pavimentos),
                -self._afinidade_total(entrada, atribuicao),
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

        for pavimento in entrada.pavimentos:
            ocupantes = [
                c for c in entrada.clinicas if atribuicao[c.id] == pavimento.id
            ]

            alocado_por_clinica: dict[int, list[int]] = {
                c.id: [0] * NUM_TURNOS for c in ocupantes
            }
            ocupacao = [0] * NUM_TURNOS
            demanda = [0] * NUM_TURNOS

            for t in range(NUM_TURNOS):
                demandas_do_turno = [c.demanda[t] for c in ocupantes]
                recebido = repartir_turno(demandas_do_turno, pavimento.capacidade)

                for clinica, quantidade in zip(ocupantes, recebido):
                    alocado_por_clinica[clinica.id][t] = quantidade

                ocupacao[t] = sum(recebido)
                demanda[t] = sum(demandas_do_turno)

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
                    capacidade=pavimento.capacidade,
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
