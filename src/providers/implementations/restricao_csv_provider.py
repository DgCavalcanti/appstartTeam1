"""Provider CSV para restrições — lê restricoes.csv e valida o contrato MVP."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.schemas import Restricao
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "sala_id", "tipo", "valor"}


def _ler_csv(caminho: Path) -> list[dict]:
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    with caminho.open(newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if not linhas:
        raise ValueError(f"Arquivo CSV vazio: {caminho}")
    return linhas


def _validar_colunas(linhas: list[dict], obrigatorias: set[str], nome: str) -> None:
    ausentes = obrigatorias - set(linhas[0].keys())
    if ausentes:
        raise ValueError(f"'{nome}' está faltando colunas obrigatórias: {sorted(ausentes)}")


class RestricaoCsvProvider(RestricaoProviderInterface):

    def __init__(self, caminho: Path = Path("data/restricoes.csv")) -> None:
        self.caminho = caminho

    def listar_restricoes(self) -> list[Restricao]:
        linhas = _ler_csv(self.caminho)
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho.name)

        restricoes: list[Restricao] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                restricoes.append(Restricao(
                    id=linha["id"].strip(),
                    sala_id=linha["sala_id"].strip(),
                    tipo=linha["tipo"].strip(),
                    valor=linha["valor"].strip(),
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            raise ValueError(f"restricoes.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("restricoes.csv carregado: %d registros", len(restricoes))
        return restricoes
