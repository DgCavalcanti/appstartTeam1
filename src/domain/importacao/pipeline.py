"""
pipeline.py — Orquestra os 10 passos do tratamento de importação.

A ordem dos passos importa: filtrar antes de deduplicar evita que uma linha
inativa "salve" um slot que deveria sair, e deduplicar antes de contar evita
inflar a demanda com as várias condições de atendimento de um mesmo médico.

Os passos 1–8 acontecem em memória. Só o `grade_slot` e o `grade_demanda`
derivado são materializados — as linhas brutas do AGHU não persistem.

Referência: SAA_Arquitetura.pdf, seção 6.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.domain.entidades import NUM_TURNOS, Clinica, indice_turno
from src.domain.importacao.leitor import (
    descartar_colunas_irrelevantes,
    ler_planilha,
)
from src.domain.importacao.regras import (
    GradeDemanda,
    GradeSlot,
    derivar_demanda,
    deduplicar_em_slots,
    e_noite,
    e_sabado_ou_domingo,
    filtrar_condicao_de_atendimento,
    filtrar_dias,
    filtrar_situacao,
    filtrar_turno_noite,
    filtrar_unidades,
    normalizar,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Catálogos globais (passo 10)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Catalogo:
    """
    O que o sistema já conhece de importações anteriores.

    Sobrevive entre cenários e pré-preenche cada nova alocação.

    Os nomes são normalizados na construção, então pode-se passar a grafia
    natural — 'FARMÁCIA CENTRAL' e 'farmacia central' são o mesmo item. Sem
    isso, um acento fora do lugar faria o filtro do passo 2 virar um no-op
    silencioso, deixando passar unidades que não deveriam participar.
    """

    #: Unidades já vistas alguma vez. O que não está aqui é novidade.
    unidades_conhecidas: frozenset[str] = frozenset()
    #: Unidades marcadas como "não participa" — descartadas no passo 2.
    unidades_excluidas: frozenset[str] = frozenset()
    #: Condições de atendimento já vistas.
    condicoes_conhecidas: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        for campo in (
            "unidades_conhecidas",
            "unidades_excluidas",
            "condicoes_conhecidas",
        ):
            valores = getattr(self, campo)
            normalizados = frozenset(
                chave for chave in (normalizar(v) for v in valores) if chave
            )
            object.__setattr__(self, campo, normalizados)

    @classmethod
    def vazio(cls) -> "Catalogo":
        """Catálogo da primeira importação: tudo é novidade, nada é excluído."""
        return cls()


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RelatorioImportacao:
    """
    O que entrou, o que saiu e por quê.

    Existe para o gestor entender a redução — especialmente quantos slots foram
    perdidos no descarte do turno Noite, que o documento pede para registrar.
    """

    linhas_brutas: int
    descartadas_por_situacao: int
    descartadas_por_condicao: int
    descartadas_por_unidade: int
    descartadas_por_dia: int
    descartadas_por_noite: int
    linhas_apos_filtros: int
    total_slots: int
    slots_em_revisao: int
    total_demandas: int

    @property
    def percentual_apos_filtros(self) -> float:
        return self._percentual(self.linhas_apos_filtros)

    @property
    def percentual_slots(self) -> float:
        return self._percentual(self.total_slots)

    @property
    def percentual_demandas(self) -> float:
        return self._percentual(self.total_demandas)

    def _percentual(self, valor: int) -> float:
        if self.linhas_brutas == 0:
            return 0.0
        return 100.0 * valor / self.linhas_brutas

    def resumo(self) -> str:
        """Texto de uma linha por etapa, no formato da tabela da seção 6."""
        return "\n".join(
            [
                f"Bruto do AGHU                {self.linhas_brutas:>6}  100%",
                f"Após filtros                 {self.linhas_apos_filtros:>6}  "
                f"{self.percentual_apos_filtros:>3.0f}%",
                f"grade_slot                   {self.total_slots:>6}  "
                f"{self.percentual_slots:>3.0f}%",
                f"grade_demanda                {self.total_demandas:>6}  "
                f"{self.percentual_demandas:>3.0f}%",
            ]
        )


@dataclass(frozen=True)
class ResultadoImportacao:
    """Tudo o que a etapa 1 entrega para as etapas seguintes."""

    slots: tuple[GradeSlot, ...]
    demandas: tuple[GradeDemanda, ...]
    relatorio: RelatorioImportacao
    #: Passo 10 — unidades nunca vistas. O gestor decide se entram na alocação.
    unidades_novas: tuple[str, ...] = field(default_factory=tuple)
    #: Passo 10 — condições de atendimento nunca vistas.
    condicoes_novas: tuple[str, ...] = field(default_factory=tuple)

    @property
    def precisa_de_reconciliacao(self) -> bool:
        """Há novidade a confirmar com o gestor antes de seguir para a etapa 2?"""
        return bool(self.unidades_novas or self.condicoes_novas)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def executar_pipeline(
    df: pd.DataFrame, catalogo: Catalogo | None = None
) -> ResultadoImportacao:
    """
    Passos 2 a 10 sobre um DataFrame já lido.

    Separado de `importar` para que os testes possam montar o DataFrame na mão,
    sem tocar em disco.
    """
    catalogo = catalogo or Catalogo.vazio()
    linhas_brutas = len(df)

    # Passo 10 (detecção) — o que há de novo em relação ao catálogo.
    # Feito sobre o bruto, antes de qualquer filtro: uma unidade nova que seria
    # descartada ainda precisa ser apresentada ao gestor.
    unidades_novas = _novidades(df, "Unidade_Funcional", catalogo.unidades_conhecidas)
    condicoes_novas = _novidades(
        df, "Condicao_De_Atendimento", catalogo.condicoes_conhecidas
    )

    # Passo 6 — fora as colunas que não entram na alocação.
    df = descartar_colunas_irrelevantes(df)

    # Passo 4 — só grade e horário ativos.
    antes = len(df)
    df = filtrar_situacao(df)
    descartadas_por_situacao = antes - len(df)

    # Passo 3 — fora as condições que não ocupam sala.
    antes = len(df)
    df = filtrar_condicao_de_atendimento(df)
    descartadas_por_condicao = antes - len(df)

    # Passo 2 — fora as unidades que não participam.
    antes = len(df)
    df = filtrar_unidades(df, catalogo.unidades_excluidas)
    descartadas_por_unidade = antes - len(df)

    # Passo 5 — fora o sábado.
    antes = len(df)
    df = filtrar_dias(df)
    descartadas_por_dia = antes - len(df)

    # Passo 7 — fora o turno Noite, contando quantos saíram.
    antes = len(df)
    df = filtrar_turno_noite(df)
    descartadas_por_noite = antes - len(df)
    if descartadas_por_noite:
        logger.info(
            "turno Noite descartado: %d linhas saíram", descartadas_por_noite
        )

    linhas_apos_filtros = len(df)

    # Passo 8 — deduplicar em slots, marcando os casos de revisão.
    slots = deduplicar_em_slots(df)

    # Passo 9 — derivar as contagens.
    demandas = derivar_demanda(slots)

    relatorio = RelatorioImportacao(
        linhas_brutas=linhas_brutas,
        descartadas_por_situacao=descartadas_por_situacao,
        descartadas_por_condicao=descartadas_por_condicao,
        descartadas_por_unidade=descartadas_por_unidade,
        descartadas_por_dia=descartadas_por_dia,
        descartadas_por_noite=descartadas_por_noite,
        linhas_apos_filtros=linhas_apos_filtros,
        total_slots=len(slots),
        slots_em_revisao=sum(1 for s in slots if s.revisar),
        total_demandas=len(demandas),
    )

    logger.info(
        "importação concluída: %d → %d linhas → %d slots → %d demandas",
        linhas_brutas,
        linhas_apos_filtros,
        len(slots),
        len(demandas),
    )

    return ResultadoImportacao(
        slots=slots,
        demandas=demandas,
        relatorio=relatorio,
        unidades_novas=unidades_novas,
        condicoes_novas=condicoes_novas,
    )


def importar(
    caminho: str | Path, catalogo: Catalogo | None = None
) -> ResultadoImportacao:
    """Passo 1 + passos 2 a 10: lê a planilha do AGHU e trata os dados."""
    return executar_pipeline(ler_planilha(caminho), catalogo)


def _novidades(
    df: pd.DataFrame, coluna: str, conhecidos: frozenset[str]
) -> tuple[str, ...]:
    """Valores da coluna que o catálogo ainda não conhece, na grafia original."""
    if coluna not in df.columns:
        return ()
    vistos: dict[str, str] = {}
    for valor in df[coluna].dropna().unique():
        chave = normalizar(valor)
        if chave and chave not in conhecidos:
            vistos.setdefault(chave, str(valor).strip())
    return tuple(sorted(vistos.values()))


# ---------------------------------------------------------------------------
# Ponte para o motor de alocação
# ---------------------------------------------------------------------------


def para_clinicas(demandas: tuple[GradeDemanda, ...]) -> tuple[Clinica, ...]:
    """
    Converte as contagens de `grade_demanda` nos vetores de 10 turnos que o
    motor consome.

    Os ids são atribuídos em ordem alfabética de unidade, de modo que a mesma
    importação sempre produza as mesmas clínicas com os mesmos ids.
    """
    vetores: dict[str, list[int]] = {}
    for demanda in demandas:
        vetor = vetores.setdefault(demanda.unidade, [0] * NUM_TURNOS)
        vetor[indice_turno(demanda.dia, demanda.periodo)] += demanda.quantidade

    return tuple(
        Clinica(id=i, nome=nome, demanda=tuple(vetores[nome]))
        for i, nome in enumerate(sorted(vetores), start=1)
    )
