"""
leitor.py — Passo 1 do pipeline: ler a grade exportada do AGHU.

Aceita .xlsx e .csv. A única responsabilidade aqui é entregar um DataFrame com
as colunas esperadas; nenhuma regra de negócio mora neste módulo.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


#: Colunas que o pipeline consome. As demais são descartadas no passo 6.
COLUNAS_NECESSARIAS: tuple[str, ...] = (
    "Profissional_Grade",
    "Unidade_Funcional",
    "Condicao_De_Atendimento",
    "Situacao_Atual_Grade",
    "Situacao_Atual_Horario",
    "Dia_da_Semana",
    "Turno",
)

#: Colunas que a exportação traz mas a alocação ignora (passo 6).
#: Vale o turno completo, então o horário exato não importa, e a quantidade de
#: vagas não afeta ocupação de sala.
#:
#: `Especialidade` NÃO entra aqui: ela nunca decide pavimento nem demanda
#: agregada, mas é preservada como dado auxiliar de auditoria em `grade_slot`
#: (ver `regras.deduplicar_em_slots`). Descartá-la aqui apagaria essa
#: informação antes mesmo de o passo 8 poder carregá-la.
COLUNAS_IRRELEVANTES: tuple[str, ...] = (
    "Hora_Inicio",
    "Hora_Início",
    "Quantidade_Vagas",
    "Grade",
)

#: Encodings tentados em ordem. O AGHU costuma exportar UTF-8 com BOM, mas
#: planilhas salvas manualmente no Excel pt-BR saem em Latin-1.
_ENCODINGS = ("utf-8-sig", "utf-8", "latin-1")


class ErroDeLeitura(Exception):
    """A planilha não pôde ser lida ou não tem o formato esperado."""


def ler_planilha(caminho: str | Path) -> pd.DataFrame:
    """
    Lê a exportação do AGHU e devolve o DataFrame bruto.

    Levanta ErroDeLeitura se o arquivo não existir, tiver extensão não
    suportada ou não trouxer as colunas que o pipeline precisa.
    """
    caminho = Path(caminho)
    if not caminho.exists():
        raise ErroDeLeitura(f"arquivo não encontrado: {caminho}")

    sufixo = caminho.suffix.lower()
    if sufixo in (".xlsx", ".xls"):
        df = pd.read_excel(caminho, dtype=str)
    elif sufixo == ".csv":
        df = _ler_csv(caminho)
    else:
        raise ErroDeLeitura(
            f"extensão não suportada: {sufixo!r}. Esperado .xlsx, .xls ou .csv"
        )

    _validar_colunas(df, caminho)
    logger.info("planilha lida: %s (%d linhas)", caminho.name, len(df))
    return df


def _ler_csv(caminho: Path) -> pd.DataFrame:
    ultimo_erro: Exception | None = None
    for encoding in _ENCODINGS:
        try:
            return pd.read_csv(caminho, dtype=str, encoding=encoding)
        except UnicodeDecodeError as erro:
            ultimo_erro = erro
            continue
    raise ErroDeLeitura(
        f"não foi possível decodificar {caminho.name}; tentados: {_ENCODINGS}"
    ) from ultimo_erro


def _validar_colunas(df: pd.DataFrame, caminho: Path) -> None:
    faltando = [c for c in COLUNAS_NECESSARIAS if c not in df.columns]
    if faltando:
        raise ErroDeLeitura(
            f"{caminho.name}: colunas ausentes: {faltando}. "
            f"Colunas encontradas: {list(df.columns)}"
        )


def descartar_colunas_irrelevantes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Passo 6 — remove as colunas que não entram na alocação.

    Fazer isso cedo reduz o DataFrame que circula pelos passos seguintes.
    """
    presentes = [c for c in COLUNAS_IRRELEVANTES if c in df.columns]
    if presentes:
        logger.debug("descartando colunas irrelevantes: %s", presentes)
    return df.drop(columns=presentes)
