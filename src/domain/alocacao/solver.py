"""
solver.py — Contrato do motor de alocação.

Define a entrada, a saída e a interface `SolverAlocacao`. A heurística (e, um
dia, um solver exato) implementam esta interface; o resto do sistema conhece
apenas o contrato.

Referência: SAA_Arquitetura.pdf, seção 8.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol

from src.domain.entidades import NUM_TURNOS, Clinica, Pavimento


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntradaAlocacao:
    """
    Tudo o que o motor precisa para resolver um cenário.

    Campos:
        clinicas     — unidades funcionais com seu vetor de demanda (10 turnos)
        pavimentos   — pavimentos com capacidade em estações
        obrigatorias — clinica_id → pavimento_id. Trava rígida: a clínica vai
                       para lá mesmo que gere sobra.
        afinidade    — (clinica_id, pavimento_id) → nota. Quanto maior, mais a
                       clínica "quer" aquele pavimento. Combina a preferência
                       manual do gestor com o histórico. Ausente significa 0.
        alocacao_atual — clinica_id → pavimento_id de onde a clínica está hoje
                       (execução anterior do motor OU ajuste manual do gestor —
                       tratados de forma uniforme). Usado só como preferência de
                       estabilidade de MENOR prioridade (nível 6 da hierarquia de
                       objetivos): entre soluções empatadas em sobra, afinidade e
                       equilíbrio proporcional, o motor prefere mexer em menos
                       clínicas. Nunca vira obrigatoriedade. Ausente/vazio
                       significa "sem preferência de estabilidade para essa
                       clínica" — não é erro.
    """

    clinicas: tuple[Clinica, ...]
    pavimentos: tuple[Pavimento, ...]
    obrigatorias: Mapping[int, int] = field(default_factory=dict)
    afinidade: Mapping[tuple[int, int], float] = field(default_factory=dict)
    alocacao_atual: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ids_clinicas = {c.id for c in self.clinicas}
        if len(ids_clinicas) != len(self.clinicas):
            raise ValueError("há clínicas com id repetido")

        ids_pavimentos = {p.id for p in self.pavimentos}
        if len(ids_pavimentos) != len(self.pavimentos):
            raise ValueError("há pavimentos com id repetido")

        if self.clinicas and not self.pavimentos:
            raise ValueError("há clínicas para alocar, mas nenhum pavimento")

        for clinica_id, pavimento_id in self.obrigatorias.items():
            if clinica_id not in ids_clinicas:
                raise ValueError(
                    f"obrigatoriedade aponta para clínica inexistente: {clinica_id}"
                )
            if pavimento_id not in ids_pavimentos:
                raise ValueError(
                    f"obrigatoriedade da clínica {clinica_id} aponta para "
                    f"pavimento inexistente: {pavimento_id}"
                )


# ---------------------------------------------------------------------------
# Saída
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResultadoClinica:
    """
    O destino de uma clínica e o desfecho da sua demanda, turno a turno.

    `alocado[t] + nao_alocado[t]` é sempre igual à demanda original no turno.
    """

    clinica_id: int
    nome: str
    pavimento_id: int
    alocado: tuple[int, ...]
    nao_alocado: tuple[int, ...]

    @property
    def total_alocado(self) -> int:
        return sum(self.alocado)

    @property
    def total_nao_alocado(self) -> int:
        return sum(self.nao_alocado)


@dataclass(frozen=True)
class OcupacaoPavimento:
    """Indicadores de um pavimento após a alocação."""

    pavimento_id: int
    nome: str
    capacidade: int
    #: Estações efetivamente usadas em cada turno (nunca acima da capacidade).
    ocupacao: tuple[int, ...]
    #: Estações pedidas em cada turno — pode passar da capacidade sob obrigatoriedade.
    demanda: tuple[int, ...]

    @property
    def ocupacao_media(self) -> float:
        """Fração média da capacidade em uso ao longo dos 10 turnos (0 a 1)."""
        if self.capacidade == 0:
            return 0.0
        return sum(self.ocupacao) / (self.capacidade * NUM_TURNOS)

    @property
    def ocupacao_pico(self) -> float:
        """Fração da capacidade em uso no turno mais cheio (0 a 1)."""
        if self.capacidade == 0:
            return 0.0
        return max(self.ocupacao) / self.capacidade


@dataclass(frozen=True)
class ResultadoAlocacao:
    """
    Resultado completo de uma execução do motor.

    Os três últimos campos são indicadores novos da Fase 2 — refletem os
    níveis 4, 5 e 6 da hierarquia de objetivos do placar de melhoria
    (heuristica.py, `_passada_de_melhoria`). Têm default para não quebrar quem
    já constrói `ResultadoAlocacao` sem eles.
    """

    por_clinica: tuple[ResultadoClinica, ...]
    por_pavimento: tuple[OcupacaoPavimento, ...]
    #: Nível 4: Σ_{p,t} |L_p,t·C - D_t·c_p| na solução final — desvio agregado
    #: da carga-alvo proporcional. Zero é equilíbrio perfeito.
    desvio_proporcional_total: int = 0
    #: Nível 5: maior |L_p,t·C - D_t·c_p| isolado — pior desequilíbrio pontual.
    pior_desequilibrio_pontual: int = 0
    #: Nível 6: nº de clínicas cujo pavimento final difere de
    #: `EntradaAlocacao.alocacao_atual` (execução anterior ou ajuste manual).
    clinicas_movidas: int = 0

    @property
    def total_nao_alocado(self) -> int:
        """Grades que ficaram sem estação. Zero é o cenário ideal."""
        return sum(r.total_nao_alocado for r in self.por_clinica)

    @property
    def total_alocado(self) -> int:
        return sum(r.total_alocado for r in self.por_clinica)

    def pavimento_da_clinica(self, clinica_id: int) -> int:
        """Atalho de leitura usado pelos testes e pela camada de serviços."""
        for resultado in self.por_clinica:
            if resultado.clinica_id == clinica_id:
                return resultado.pavimento_id
        raise KeyError(f"clínica {clinica_id} não está no resultado")


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class SolverAlocacao(Protocol):
    """
    Estratégia de alocação.

    Trocar a heurística por um solver exato significa escrever outra classe que
    satisfaça este protocolo — nada além do ponto de construção muda.
    """

    def resolver(self, entrada: EntradaAlocacao) -> ResultadoAlocacao:
        ...
