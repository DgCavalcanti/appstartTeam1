"""
regras.py — As regras do tratamento de importação (passos 2 a 9).

Funções puras sobre texto e sobre DataFrame. Cada regra corresponde a um passo
numerado da seção 6 do SAA_Arquitetura.pdf e pode ser testada isoladamente.
"""

from __future__ import annotations

import logging
import unicodedata
from dataclasses import dataclass

import pandas as pd

from src.domain.entidades import DIAS, PERIODOS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalização de texto
# ---------------------------------------------------------------------------


def normalizar(texto: object) -> str:
    """
    Reduz um valor da planilha à sua forma comparável.

    Remove acentos, baixa a caixa e colapsa espaços. É o que permite casar
    'Terça', 'TERCA' e ' terça ' como o mesmo dia, sem depender de como o AGHU
    (ou o Excel do gestor) gravou o texto.
    """
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return ""
    sem_acento = unicodedata.normalize("NFKD", str(texto))
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


# ---------------------------------------------------------------------------
# Vocabulário do AGHU
# ---------------------------------------------------------------------------

#: Passo 3 — condições que não ocupam consultório e portanto não geram demanda.
CONDICOES_SEM_SALA: frozenset[str] = frozenset(
    {
        "registro em prontuario",
        "sessao",
        "teleatendimento",
    }
)

#: Passo 4 — só grades e horários ativos entram.
SITUACAO_ATIVA: str = "ativo"

#: Passo 5 — sábado (e domingo, se aparecer) não entram na malha de 10 turnos.
DIAS_DESCARTADOS: frozenset[str] = frozenset({"sabado", "domingo"})

#: Passo 7 — o AGHU traz Noite além de manhã/tarde; nesta versão é descartado.
PERIODO_DESCARTADO: str = "noite"


def canonizar_dia(valor: object) -> str | None:
    """
    Converte o dia da planilha na forma canônica do domínio.

    Devolve None quando o dia não pertence à malha de 10 turnos — sábado,
    domingo ou lixo. O chamador decide se conta como descarte ou como erro.
    Aceita tanto 'Segunda' quanto 'Segunda-feira'.
    """
    texto = normalizar(valor)
    if not texto:
        return None
    base = texto.split("-")[0].strip()
    if base in DIAS:
        return base
    if base in DIAS_DESCARTADOS:
        return None
    return None


def canonizar_periodo(valor: object) -> str | None:
    """
    Converte o turno da planilha em 'manha' ou 'tarde'.

    Devolve None para 'Noite' (descartado nesta versão) e para valores
    desconhecidos.
    """
    texto = normalizar(valor)
    if texto in PERIODOS:
        return texto
    return None


def e_noite(valor: object) -> bool:
    """O turno é 'Noite'? Precisamos contar quantos slots saem por esse motivo."""
    return normalizar(valor) == PERIODO_DESCARTADO


def e_sabado_ou_domingo(valor: object) -> bool:
    """O dia é de fim de semana? Contado à parte no relatório."""
    return normalizar(valor).split("-")[0].strip() in DIAS_DESCARTADOS


# ---------------------------------------------------------------------------
# Filtros (passos 2 a 5, e 7)
# ---------------------------------------------------------------------------


def filtrar_unidades(
    df: pd.DataFrame, unidades_excluidas: frozenset[str]
) -> pd.DataFrame:
    """
    Passo 2 — descarta as unidades marcadas como "não participa".

    A lista vem do catálogo de unidades; comparação por forma normalizada.
    """
    if not unidades_excluidas:
        return df
    mascara = ~df["Unidade_Funcional"].map(normalizar).isin(unidades_excluidas)
    return df[mascara]


def filtrar_condicao_de_atendimento(df: pd.DataFrame) -> pd.DataFrame:
    """
    Passo 3 — remove as condições que não ocupam sala.

    Registro em Prontuário, Sessão e Teleatendimento não consomem consultório.
    """
    mascara = ~df["Condicao_De_Atendimento"].map(normalizar).isin(CONDICOES_SEM_SALA)
    return df[mascara]


def filtrar_situacao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Passo 4 — mantém apenas Situação Atual Grade E Situação Atual Horário = Ativo.

    As duas precisam estar ativas: uma grade ativa com horário inativo não gera
    atendimento.
    """
    grade_ativa = df["Situacao_Atual_Grade"].map(normalizar) == SITUACAO_ATIVA
    horario_ativo = df["Situacao_Atual_Horario"].map(normalizar) == SITUACAO_ATIVA
    return df[grade_ativa & horario_ativo]


def filtrar_dias(df: pd.DataFrame) -> pd.DataFrame:
    """Passo 5 — desconsidera sábado (e qualquer dia fora da malha de 5 dias)."""
    mascara = df["Dia_da_Semana"].map(lambda v: canonizar_dia(v) is not None)
    return df[_como_booleano(mascara)]


def filtrar_turno_noite(df: pd.DataFrame) -> pd.DataFrame:
    """Passo 7 — descarta o turno Noite (modelo de 10 turnos nesta versão)."""
    mascara = df["Turno"].map(lambda v: canonizar_periodo(v) is not None)
    return df[_como_booleano(mascara)]


def _como_booleano(mascara: pd.Series) -> pd.Series:
    """
    Garante que a máscara tenha dtype bool.

    Num DataFrame vazio, `.map()` devolve dtype object. O pandas então
    interpreta `df[mascara]` como seleção de COLUNAS em vez de linhas, e o
    DataFrame perde todas as colunas — quebrando o filtro seguinte. Isso
    acontece sempre que os filtros anteriores zeram a planilha.
    """
    return mascara.astype(bool)


# ---------------------------------------------------------------------------
# Saída do tratamento — as duas camadas da demanda (passo 9)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GradeSlot:
    """
    Camada de origem: uma linha por profissional × unidade × dia × turno.

    É o grão auditável da demanda — permite rastrear de onde veio cada número e
    reprocessar sem reimportar. Um slot ocupa uma estação.

    `revisar` marca os casos em que o mesmo profissional aparece em duas ou mais
    clínicas no mesmo turno (~7% dos casos no arquivo real). Ele NÃO conta em
    mais de uma: o passo 8 mantém um único slot, numa unidade só escolhida de
    forma determinística, e destaca o caso para o gestor conferir na etapa 2.
    """

    profissional: str
    unidade: str
    dia: str
    periodo: str
    revisar: bool = False
    #: Dado auxiliar de auditoria — NUNCA entra na chave de deduplicação nem na
    #: demanda agregada. Unidade_Funcional é quem decide pavimento; Especialidade
    #: só acompanha o slot para o gestor conferir/rastrear a origem do registro.
    #: Quando a planilha traz mais de uma especialidade para o mesmo slot (várias
    #: condições de atendimento colapsadas no passo 8), guarda todas, unidas por
    #: "; ", em ordem alfabética — determinístico e não perde informação.
    especialidade: str | None = None

    @property
    def chave(self) -> tuple[str, str, str, str]:
        """Chave de deduplicação do passo 8. Especialidade não participa dela."""
        return (self.profissional, self.unidade, self.dia, self.periodo)


@dataclass(frozen=True)
class GradeDemanda:
    """
    Camada derivada: contagem de grades por unidade/dia/turno.

    É o que a etapa 2 exibe e o gestor edita, e é a entrada do motor de alocação.
    """

    unidade: str
    dia: str
    periodo: str
    quantidade: int


# ---------------------------------------------------------------------------
# Passo 8 — deduplicação e marcação de revisão
# ---------------------------------------------------------------------------


def deduplicar_em_slots(df: pd.DataFrame) -> tuple[GradeSlot, ...]:
    """
    Passo 8 — colapsa as linhas em slots pela chave
    (Profissional, Unidade, Dia, Turno).

    Várias condições de atendimento do mesmo profissional, na mesma unidade e no
    mesmo turno, viram um único slot: ele ocupa uma sala só.

    Quando o mesmo profissional aparece em DUAS OU MAIS unidades no mesmo
    dia/turno, ele não pode contar em mais de uma — senão a mesma grade
    infla a demanda de duas clínicas ao mesmo tempo. Mantemos um único slot,
    na unidade escolhida de forma determinística (a de menor forma normalizada,
    para a mesma planilha sempre produzir o mesmo resultado), e o marcamos para
    revisão: é a etapa 2 quem avisa o gestor do caso ambíguo.

    A coluna Especialidade, quando presente, é carregada junto de cada slot como
    dado auxiliar (auditoria) — nunca entra na chave de deduplicação nem decide
    unidade ou pavimento algum.
    """
    if df.empty:
        return ()

    tem_especialidade = "Especialidade" in df.columns

    chaves: set[tuple[str, str, str, str]] = set()
    especialidades: dict[tuple[str, str, str, str], set[str]] = {}
    for _, linha in df.iterrows():
        dia = canonizar_dia(linha["Dia_da_Semana"])
        periodo = canonizar_periodo(linha["Turno"])
        if dia is None or periodo is None:
            # Já filtrado nos passos 5 e 7; defensivo contra chamada isolada.
            continue
        profissional = str(linha["Profissional_Grade"]).strip()
        unidade = str(linha["Unidade_Funcional"]).strip()
        chave = (profissional, unidade, dia, periodo)
        chaves.add(chave)

        if tem_especialidade:
            valor = linha["Especialidade"]
            texto = "" if valor is None or (isinstance(valor, float) and pd.isna(valor)) else str(valor).strip()
            if texto:
                especialidades.setdefault(chave, set()).add(texto)

    # Profissional que ocupa duas ou mais unidades no mesmo dia/turno.
    unidades_por_profissional_turno: dict[tuple[str, str, str], set[str]] = {}
    for profissional, unidade, dia, periodo in chaves:
        unidades_por_profissional_turno.setdefault(
            (profissional, dia, periodo), set()
        ).add(unidade)

    # Quando há conflito, escolhe UMA unidade só — a de menor forma
    # normalizada — para o slot não contar duas vezes na demanda agregada.
    unidade_escolhida: dict[tuple[str, str, str], str] = {}
    turnos_em_conflito: set[tuple[str, str, str]] = set()
    for turno_chave, unidades in unidades_por_profissional_turno.items():
        if len(unidades) > 1:
            turnos_em_conflito.add(turno_chave)
            unidade_escolhida[turno_chave] = min(unidades, key=normalizar)
        else:
            unidade_escolhida[turno_chave] = next(iter(unidades))

    chaves_mantidas = {
        chave
        for chave in chaves
        if chave[1] == unidade_escolhida[(chave[0], chave[2], chave[3])]
    }

    brutos = []
    for chave in chaves_mantidas:
        profissional, unidade, dia, periodo = chave
        brutos.append(
            GradeSlot(
                profissional=profissional,
                unidade=unidade,
                dia=dia,
                periodo=periodo,
                revisar=(profissional, dia, periodo) in turnos_em_conflito,
                especialidade=(
                    "; ".join(sorted(especialidades[chave]))
                    if chave in especialidades
                    else None
                ),
            )
        )

    slots = tuple(
        sorted(brutos, key=lambda s: (s.unidade, s.dia, s.periodo, s.profissional))
    )

    marcados = sum(1 for s in slots if s.revisar)
    if marcados:
        logger.info(
            "%d slots marcados para revisão (profissional em duas ou mais "
            "clínicas no mesmo turno; mantido em apenas uma)",
            marcados,
        )
    return slots


# ---------------------------------------------------------------------------
# Passo 9 — derivar as contagens
# ---------------------------------------------------------------------------


def derivar_demanda(slots: tuple[GradeSlot, ...]) -> tuple[GradeDemanda, ...]:
    """
    Passo 9 — deriva `grade_demanda` contando os slots por unidade/dia/turno.

    É uma projeção pura do `grade_slot`: pode ser recalculada a qualquer momento
    sem reimportar a planilha.
    """
    contagem: dict[tuple[str, str, str], int] = {}
    for slot in slots:
        chave = (slot.unidade, slot.dia, slot.periodo)
        contagem[chave] = contagem.get(chave, 0) + 1

    return tuple(
        GradeDemanda(unidade=unidade, dia=dia, periodo=periodo, quantidade=quantidade)
        for (unidade, dia, periodo), quantidade in sorted(contagem.items())
    )
