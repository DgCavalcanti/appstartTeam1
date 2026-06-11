"""
alocacao_csv_provider.py — Implementação CSV do Provider de Alocação

Lê grades, salas e histórico a partir de arquivos CSV locais.
Persiste alocações geradas em SQLite (histórico de ajustes).

Colunas obrigatórias por arquivo:
  grades.csv    : id, especialidade, profissional, dia_semana, turno, qtd_salas_necessarias
  salas.csv     : id, numero, andar, bloco, status, tem_equipamento, acessivel,
                  especialidade_preferencial, tem_maca_ginecologica
  alocacoes.csv : id, id_grade, id_sala, dia_semana, turno, status  (histórico anterior — opcional)
"""
from __future__ import annotations

import csv
import logging
import sqlite3
from pathlib import Path
from typing import Optional

from src.models.schemas import Alocacao, Grade, Sala
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface

logger = logging.getLogger(__name__)

# Colunas obrigatórias por arquivo CSV
COLUNAS_GRADES   = {"id", "especialidade", "profissional", "dia_semana", "turno", "qtd_salas_necessarias"}
COLUNAS_SALAS    = {"id", "numero", "andar", "bloco", "status", "tem_equipamento", "acessivel"}
COLUNAS_ALOCACAO = {"id", "id_grade", "id_sala", "dia_semana", "turno", "status"}


# ---------------------------------------------------------------------------
# Helpers de leitura CSV
# ---------------------------------------------------------------------------

def _ler_csv(caminho: Path) -> list[dict]:
    """Lê um CSV e retorna lista de dicts. Lança ValueError se vazio ou ausente."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    with caminho.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        linhas = list(reader)

    if not linhas:
        raise ValueError(f"Arquivo CSV vazio: {caminho}")

    return linhas


def _validar_colunas(linhas: list[dict], obrigatorias: set[str], nome_arquivo: str) -> None:
    """Garante que todas as colunas obrigatórias estão presentes. RNF004/RNF005."""
    colunas_presentes = set(linhas[0].keys())
    ausentes = obrigatorias - colunas_presentes
    if ausentes:
        raise ValueError(
            f"Arquivo '{nome_arquivo}' está faltando colunas obrigatórias: {sorted(ausentes)}"
        )


def _parse_bool(valor: str) -> bool:
    """Converte string CSV para bool. Aceita true/false/1/0 (case-insensitive)."""
    return valor.strip().lower() in ("true", "1", "sim", "s")


def _parse_optional_str(valor: str) -> Optional[str]:
    v = valor.strip()
    return v if v else None


# ---------------------------------------------------------------------------
# Implementação
# ---------------------------------------------------------------------------

class AlocacaoCsvProvider(AlocacaoProviderInterface):
    """
    Provider que lê grades e salas de CSVs e persiste alocações em SQLite.

    Parâmetros:
        caminho_grades    — path para grades.csv
        caminho_salas     — path para salas.csv
        caminho_alocacoes — path para alocacoes.csv (histórico anterior, opcional)
        caminho_db        — path para o banco SQLite de histórico
    """

    def __init__(
        self,
        caminho_grades: Path,
        caminho_salas: Path,
        caminho_alocacoes: Optional[Path] = None,
        caminho_db: Path = Path("data/historico.db"),
    ) -> None:
        self.caminho_grades    = caminho_grades
        self.caminho_salas     = caminho_salas
        self.caminho_alocacoes = caminho_alocacoes
        self.caminho_db        = caminho_db
        self._garantir_tabela_historico()

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def listar_grades(self) -> list[Grade]:
        """Lê e valida grades.csv, retorna lista de Grade."""
        linhas = _ler_csv(self.caminho_grades)
        _validar_colunas(linhas, COLUNAS_GRADES, self.caminho_grades.name)

        grades: list[Grade] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):  # start=2 porque linha 1 é o header
            try:
                grades.append(Grade(
                    id=int(linha["id"]),
                    especialidade=linha["especialidade"].strip(),
                    profissional=linha["profissional"].strip(),
                    dia_semana=linha["dia_semana"].strip(),
                    turno=linha["turno"].strip(),
                    qtd_salas_necessarias=int(linha["qtd_salas_necessarias"]),
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            logger.error("Erros ao importar grades.csv: %s", erros)
            raise ValueError(f"grades.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("grades.csv carregado: %d registros", len(grades))
        return grades

    def listar_salas(self) -> list[Sala]:
        """Lê e valida salas.csv, retorna lista de Sala."""
        linhas = _ler_csv(self.caminho_salas)
        _validar_colunas(linhas, COLUNAS_SALAS, self.caminho_salas.name)

        salas: list[Sala] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                salas.append(Sala(
                    id=int(linha["id"]),
                    numero=linha["numero"].strip(),
                    andar=linha["andar"].strip(),
                    bloco=linha["bloco"].strip(),
                    status=linha["status"].strip(),
                    tem_equipamento=_parse_bool(linha["tem_equipamento"]),
                    acessivel=_parse_bool(linha["acessivel"]),
                    especialidade_preferencial=_parse_optional_str(
                        linha.get("especialidade_preferencial", "")
                    ),
                    tem_maca_ginecologica=_parse_bool(
                        linha.get("tem_maca_ginecologica", "false")
                    ),
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            logger.error("Erros ao importar salas.csv: %s", erros)
            raise ValueError(f"salas.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("salas.csv carregado: %d registros", len(salas))
        return salas

    def listar_historico(self) -> list[Alocacao]:
        """
        Retorna histórico de alocações — combina:
          1. alocacoes.csv (se fornecido) — alocações anteriores importadas
          2. SQLite — alocações geradas pelo motor nas sessões anteriores
        """
        historico: list[Alocacao] = []

        # Fonte 1: CSV de histórico (opcional)
        if self.caminho_alocacoes and self.caminho_alocacoes.exists():
            try:
                linhas = _ler_csv(self.caminho_alocacoes)
                _validar_colunas(linhas, COLUNAS_ALOCACAO, self.caminho_alocacoes.name)
                for i, linha in enumerate(linhas, start=2):
                    try:
                        historico.append(Alocacao(
                            id=int(linha["id"]),
                            id_grade=int(linha["id_grade"]),
                            id_sala=int(linha["id_sala"]),
                            dia_semana=linha["dia_semana"].strip(),
                            turno=linha["turno"].strip(),
                            status=linha["status"].strip(),
                        ))
                    except (ValueError, KeyError) as e:
                        logger.warning("alocacoes.csv linha %d ignorada: %s", i, e)
            except (FileNotFoundError, ValueError) as e:
                logger.warning("Histórico CSV ignorado: %s", e)

        # Fonte 2: SQLite
        historico += self._ler_historico_sqlite()

        logger.info("Histórico carregado: %d registros", len(historico))
        return historico

    def salvar_alocacoes(self, alocacoes: list[Alocacao]) -> None:
        """Persiste as alocações no SQLite."""
        with sqlite3.connect(self.caminho_db) as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO historico_alocacoes
                    (id, id_grade, id_sala, dia_semana, turno, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (a.id, a.id_grade, a.id_sala, a.dia_semana, a.turno, a.status)
                    for a in alocacoes
                ],
            )
            conn.commit()
        logger.info("Alocações persistidas no SQLite: %d registros", len(alocacoes))

    # ------------------------------------------------------------------
    # SQLite — setup e leitura
    # ------------------------------------------------------------------

    def _garantir_tabela_historico(self) -> None:
        """Cria a tabela de histórico se não existir (idempotente)."""
        self.caminho_db.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.caminho_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS historico_alocacoes (
                    id          INTEGER PRIMARY KEY,
                    id_grade    INTEGER NOT NULL,
                    id_sala     INTEGER NOT NULL,
                    dia_semana  TEXT NOT NULL,
                    turno       TEXT NOT NULL,
                    status      TEXT NOT NULL
                )
            """)
            conn.commit()

    def _ler_historico_sqlite(self) -> list[Alocacao]:
        """Lê alocações previamente salvas no SQLite."""
        with sqlite3.connect(self.caminho_db) as conn:
            cursor = conn.execute(
                "SELECT id, id_grade, id_sala, dia_semana, turno, status FROM historico_alocacoes"
            )
            return [
                Alocacao(
                    id=row[0], id_grade=row[1], id_sala=row[2],
                    dia_semana=row[3], turno=row[4], status=row[5],
                )
                for row in cursor.fetchall()
            ]
