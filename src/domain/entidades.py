"""
entidades.py — Entidades e vocabulário do domínio do SAA.

Define a malha de turnos da semana e as entidades que o motor de alocação
consome. Tudo aqui é imutável e sem dependência externa.

Referência: SAA_Arquitetura.pdf, seções 5 e 8.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Malha de turnos — 10 turnos (5 dias × 2 períodos)
# ---------------------------------------------------------------------------
#
# O turno "Noite" do AGHU é descartado nesta versão (decisão fechada nº 2 da
# seção 13). Sábado também não entra (passo 5 do pipeline de importação).

DIAS: tuple[str, ...] = ("segunda", "terca", "quarta", "quinta", "sexta")
PERIODOS: tuple[str, ...] = ("manha", "tarde")

NUM_TURNOS: int = len(DIAS) * len(PERIODOS)

#: Os 10 turnos em ordem canônica: segunda-manhã, segunda-tarde, terça-manhã, ...
TURNOS: tuple[tuple[str, str], ...] = tuple(
    (dia, periodo) for dia in DIAS for periodo in PERIODOS
)


def indice_turno(dia: str, periodo: str) -> int:
    """
    Converte (dia, período) no índice do turno dentro dos vetores de demanda.

    Levanta ValueError se o dia ou o período não pertencerem à malha de 10
    turnos — o que inclui sábado e o turno "Noite", descartados na importação.
    """
    try:
        i_dia = DIAS.index(dia.strip().lower())
    except ValueError:
        raise ValueError(
            f"dia inválido: {dia!r}. Esperado um de {DIAS}"
        ) from None
    try:
        i_periodo = PERIODOS.index(periodo.strip().lower())
    except ValueError:
        raise ValueError(
            f"período inválido: {periodo!r}. Esperado um de {PERIODOS}"
        ) from None
    return i_dia * len(PERIODOS) + i_periodo


def rotulo_turno(indice: int) -> str:
    """Rótulo legível de um turno — ex.: 'segunda/manha'. Útil em logs e testes."""
    dia, periodo = TURNOS[indice]
    return f"{dia}/{periodo}"


# ---------------------------------------------------------------------------
# Capacidade — sempre contada em ESTAÇÕES
# ---------------------------------------------------------------------------
#
# Uma sala de 2 estações comporta dois atendimentos simultâneos e vale 2 na
# conta de capacidade. Guardamos as contagens por tipo (que o gestor edita na
# etapa 3) e derivamos a capacidade, evitando divergência entre os números.


def capacidade_em_estacoes(
    padrao_1est: int = 0,
    padrao_2est: int = 0,
    esp_1est: int = 0,
    esp_2est: int = 0,
) -> int:
    """
    Capacidade de um pavimento em estações.

        1×PADRÃO(1est) + 2×PADRÃO(2est) + 1×ESP(1est) + 2×ESP(2est)

    Salas fechadas não entram — elas não são contadas por nenhum dos parâmetros.
    """
    return padrao_1est + 2 * padrao_2est + esp_1est + 2 * esp_2est


def total_de_salas(
    padrao_1est: int = 0,
    padrao_2est: int = 0,
    esp_1est: int = 0,
    esp_2est: int = 0,
) -> int:
    """
    Número de salas físicas do pavimento.

    O motor raciocina em estações; os relatórios de "nº de salas" e
    "% de ocupação" usam esta contagem para voltar ao mundo físico.
    """
    return padrao_1est + padrao_2est + esp_1est + esp_2est


def salas_ocupadas(
    estacoes_em_uso: int,
    padrao_1est: int = 0,
    padrao_2est: int = 0,
    esp_1est: int = 0,
    esp_2est: int = 0,
) -> int:
    """
    Converte estações em uso de volta para salas físicas ocupadas.

    O motor conta capacidade em estações, mas o gestor pensa em salas. Esta é a
    conversão que a seção 14 do documento pede nos relatórios de "número de
    salas" e "% de ocupação".

    Preenchemos primeiro as salas de 2 estações, que rendem mais por sala — o
    que dá o menor número de salas físicas capaz de acomodar aquela ocupação.
    Uma sala de 2 estações parcialmente usada conta como uma sala ocupada.
    """
    if estacoes_em_uso <= 0:
        return 0

    restante = estacoes_em_uso
    ocupadas = 0

    # Salas de 2 estações primeiro (padrão e especializada), depois as de 1.
    for quantidade, capacidade in (
        (padrao_2est, 2),
        (esp_2est, 2),
        (padrao_1est, 1),
        (esp_1est, 1),
    ):
        while quantidade > 0 and restante > 0:
            restante -= capacidade
            ocupadas += 1
            quantidade -= 1

    # Se a ocupação passou da capacidade (só acontece sob obrigatoriedade), não
    # há mais salas físicas — a sobra fica sem sala, e o total não é inflado.
    return ocupadas


# ---------------------------------------------------------------------------
# Entidades do motor
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Clinica:
    """
    Uma unidade funcional (clínica) e seu vetor de demanda semanal.

    `demanda[t]` é quantas grades a clínica precisa atender no turno `t`,
    seguindo a ordem canônica de TURNOS. Uma grade ocupa uma estação.
    """

    id: int
    nome: str
    demanda: tuple[int, ...]

    def __post_init__(self) -> None:
        if len(self.demanda) != NUM_TURNOS:
            raise ValueError(
                f"clínica {self.nome!r}: demanda tem {len(self.demanda)} turnos, "
                f"esperado {NUM_TURNOS}"
            )
        if any(q < 0 for q in self.demanda):
            raise ValueError(f"clínica {self.nome!r}: demanda não pode ser negativa")

    @property
    def pico(self) -> int:
        """Demanda do turno mais cheio — critério de ordenação da fila."""
        return max(self.demanda)

    @property
    def total(self) -> int:
        """Soma da demanda nos 10 turnos."""
        return sum(self.demanda)


@dataclass(frozen=True)
class Pavimento:
    """
    Um pavimento do prédio e sua capacidade em estações.

    A capacidade vale igualmente nos 10 turnos — é a "caixa" onde as clínicas
    são empacotadas.
    """

    id: int
    nome: str
    capacidade: int

    def __post_init__(self) -> None:
        if self.capacidade < 0:
            raise ValueError(
                f"pavimento {self.nome!r}: capacidade não pode ser negativa"
            )


# Tipos de restrição (tabela `restricao`, seção 5)
OBRIGATORIO = "obrigatorio"
PREFERENCIAL = "preferencial"


@dataclass(frozen=True)
class Restricao:
    """
    Liga uma clínica a um pavimento.

    - `obrigatorio`: trava rígida. A clínica vai para aquele pavimento mesmo que
      isso gere grade não alocada. É a única coisa capaz de gerar sobra.
    - `preferencial`: um puxão, nunca uma imposição. Entra como afinidade e
      cede se o pavimento não comportar a clínica inteira.
    """

    clinica_id: int
    pavimento_id: int
    tipo: str

    def __post_init__(self) -> None:
        if self.tipo not in (OBRIGATORIO, PREFERENCIAL):
            raise ValueError(
                f"tipo de restrição inválido: {self.tipo!r}. "
                f"Esperado {OBRIGATORIO!r} ou {PREFERENCIAL!r}"
            )
