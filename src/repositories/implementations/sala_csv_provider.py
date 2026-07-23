"""Provider CSV para salas — lê salas.csv e valida o contrato MVP."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.schemas import Sala
from src.repositories.interfaces.sala_provider_interface import SalaProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "numero", "bloco", "andar", "status", "acessibilidade", "equipamentos"}


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


def _parse_bool(valor: str) -> bool:
    return valor.strip().lower() in ("true", "1", "sim", "s")


def _parse_equipamentos(valor: str) -> list[str]:
    if not valor or not valor.strip():
        return []
    return [e.strip() for e in valor.split(";") if e.strip()]


class SalaCsvProvider(SalaProviderInterface):

    def __init__(self, caminho: Path = Path("data/salas.csv")) -> None:
        self.caminho = caminho

    def listar_salas(self) -> list[Sala]:
        linhas = _ler_csv(self.caminho)
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho.name)

        salas: list[Sala] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                esp_pref = linha.get("especialidade_preferencial", "").strip() or None
                salas.append(Sala(
                    id=linha["id"].strip(),
                    numero=linha["numero"].strip(),
                    bloco=linha["bloco"].strip(),
                    andar=linha["andar"].strip(),
                    status=linha["status"].strip(),
                    acessibilidade=_parse_bool(linha["acessibilidade"]),
                    equipamentos=_parse_equipamentos(linha.get("equipamentos", "")),
                    especialidade_preferencial=esp_pref,
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            raise ValueError(f"salas.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("salas.csv carregado: %d registros", len(salas))
        return salas

    def buscar_sala(self, sala_id: str) -> Sala | None:
        return next((s for s in self.listar_salas() if s.id == sala_id), None)
