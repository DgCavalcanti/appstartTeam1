"""Provider SQLite para histórico de ajustes manuais de alocação."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from src.models.schemas import Conflito, HistoricoAjuste
from src.repositories.interfaces.historico_provider_interface import HistoricoProviderInterface

logger = logging.getLogger(__name__)


class HistoricoSqliteProvider(HistoricoProviderInterface):

    def __init__(self, caminho_db: Path = Path("data/saa.db")) -> None:
        self.caminho_db = caminho_db
        self._garantir_tabela()

    def registrar(self, entrada: HistoricoAjuste) -> None:
        with sqlite3.connect(self.caminho_db) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO historico_ajustes
                    (id, alocacao_id, sala_anterior_id, sala_nova_id,
                     data_hora, usuario, justificativa,
                     conflitos_antes, conflitos_depois)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entrada.id,
                    entrada.alocacao_id,
                    entrada.sala_anterior_id,
                    entrada.sala_nova_id,
                    entrada.data_hora,
                    entrada.usuario,
                    entrada.justificativa,
                    json.dumps([c.model_dump() for c in entrada.conflitos_antes], ensure_ascii=False),
                    json.dumps([c.model_dump() for c in entrada.conflitos_depois], ensure_ascii=False),
                ),
            )
            conn.commit()
        logger.info("Histórico registrado: %s", entrada.id)

    def listar(self) -> list[HistoricoAjuste]:
        with sqlite3.connect(self.caminho_db) as conn:
            cursor = conn.execute(
                """
                SELECT id, alocacao_id, sala_anterior_id, sala_nova_id,
                       data_hora, usuario, justificativa,
                       conflitos_antes, conflitos_depois
                FROM historico_ajustes
                ORDER BY data_hora DESC
                """
            )
            return [
                HistoricoAjuste(
                    id=r[0],
                    alocacao_id=r[1],
                    sala_anterior_id=r[2],
                    sala_nova_id=r[3],
                    data_hora=r[4],
                    usuario=r[5],
                    justificativa=r[6],
                    conflitos_antes=[Conflito(**c) for c in json.loads(r[7] or "[]")],
                    conflitos_depois=[Conflito(**c) for c in json.loads(r[8] or "[]")],
                )
                for r in cursor.fetchall()
            ]

    def _garantir_tabela(self) -> None:
        self.caminho_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.caminho_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historico_ajustes (
                    id               TEXT PRIMARY KEY,
                    alocacao_id      TEXT NOT NULL,
                    sala_anterior_id TEXT NOT NULL,
                    sala_nova_id     TEXT NOT NULL,
                    data_hora        TEXT NOT NULL,
                    usuario          TEXT NOT NULL,
                    justificativa    TEXT,
                    conflitos_antes  TEXT,
                    conflitos_depois TEXT
                )
            """)
            conn.commit()
