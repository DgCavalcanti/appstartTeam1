"""Provider CSV/SQLite para alocações SAA — lê alocacoes.csv, persiste ajustes em SQLite."""
from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path

from src.models.schemas import Alocacao
from src.providers.interfaces.historico_provider_interface import AlocacaoSaaProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "grade_id", "sala_id", "dia_semana", "turno"}


def _ler_csv(caminho: Path) -> list[dict]:
    """Lê o CSV de alocações. Um arquivo só com cabeçalho (sem linhas de
    dados) é um estado válido — significa simplesmente que ainda não há
    nenhuma alocação registrada (ex.: ao começar a usar a grade real do
    AGHU, antes de qualquer alocação manual)."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")
    with caminho.open(newline="", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return linhas


def _validar_colunas(linhas: list[dict], obrigatorias: set[str], nome: str) -> None:
    ausentes = obrigatorias - set(linhas[0].keys())
    if ausentes:
        raise ValueError(f"'{nome}' está faltando colunas obrigatórias: {sorted(ausentes)}")


class AlocacaoSaaCsvProvider(AlocacaoSaaProviderInterface):
    """
    Lê alocações do CSV base e sobrescreve com ajustes manuais armazenados no SQLite.
    Garante que mudanças manuais persistam entre reinicializações sem alterar o CSV original.
    """

    def __init__(
        self,
        caminho_alocacoes: Path = Path("data/alocacoes.csv"),
        caminho_db: Path = Path("data/saa.db"),
    ) -> None:
        self.caminho_alocacoes = caminho_alocacoes
        self.caminho_db = caminho_db
        self._garantir_tabela_alocacoes()

    # ── Interface pública ─────────────────────────────────────────────────────

    def listar_alocacoes(self) -> list[Alocacao]:
        """Retorna alocações CSV sobrescritas pelos ajustes manuais do SQLite."""
        base = self._ler_csv_alocacoes()
        ajustes = {a.id: a for a in self._ler_sqlite_alocacoes()}

        resultado = []
        for aloc in base:
            resultado.append(ajustes.get(aloc.id, aloc))

        logger.info("Alocações carregadas: %d registros", len(resultado))
        return resultado

    def buscar_alocacao(self, alocacao_id: str) -> Alocacao | None:
        return next((a for a in self.listar_alocacoes() if a.id == alocacao_id), None)

    def atualizar_alocacao(self, alocacao: Alocacao) -> None:
        """Persiste o ajuste manual no SQLite (INSERT OR REPLACE)."""
        with sqlite3.connect(self.caminho_db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO alocacoes_ajustes
                    (id, grade_id, sala_id, dia_semana, turno)
                VALUES (?, ?, ?, ?, ?)
                """,
                (alocacao.id, alocacao.grade_id, alocacao.sala_id,
                 alocacao.dia_semana, alocacao.turno),
            )
            conn.commit()
        logger.info("Alocação %s atualizada para sala %s", alocacao.id, alocacao.sala_id)

    # ── Internos ──────────────────────────────────────────────────────────────

    def _ler_csv_alocacoes(self) -> list[Alocacao]:
        linhas = _ler_csv(self.caminho_alocacoes)
        if not linhas:
            return []
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho_alocacoes.name)
        alocacoes: list[Alocacao] = []
        for i, linha in enumerate(linhas, start=2):
            try:
                alocacoes.append(Alocacao(
                    id=linha["id"].strip(),
                    grade_id=linha["grade_id"].strip(),
                    sala_id=linha["sala_id"].strip(),
                    dia_semana=linha["dia_semana"].strip(),
                    turno=linha["turno"].strip(),
                ))
            except (ValueError, KeyError) as e:
                logger.warning("alocacoes.csv linha %d ignorada: %s", i, e)
        return alocacoes

    def _ler_sqlite_alocacoes(self) -> list[Alocacao]:
        with sqlite3.connect(self.caminho_db) as conn:
            cursor = conn.execute(
                "SELECT id, grade_id, sala_id, dia_semana, turno FROM alocacoes_ajustes"
            )
            return [
                Alocacao(id=r[0], grade_id=r[1], sala_id=r[2], dia_semana=r[3], turno=r[4])
                for r in cursor.fetchall()
            ]

    def _garantir_tabela_alocacoes(self) -> None:
        self.caminho_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.caminho_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alocacoes_ajustes (
                    id          TEXT PRIMARY KEY,
                    grade_id    TEXT NOT NULL,
                    sala_id     TEXT NOT NULL,
                    dia_semana  TEXT NOT NULL,
                    turno       TEXT NOT NULL
                )
            """)
            conn.commit()
