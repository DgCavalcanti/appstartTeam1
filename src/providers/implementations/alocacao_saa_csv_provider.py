"""Provider CSV/SQLite para alocações SAA — lê alocacoes.csv, persiste ajustes em SQLite."""
from __future__ import annotations

import csv
import io
import logging
import sqlite3
from pathlib import Path

from src.models.schemas import Alocacao
from src.providers.interfaces.historico_provider_interface import AlocacaoSaaProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "grade_id", "sala_id", "dia_semana", "turno"}


def _detectar_encoding(caminho: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            caminho.read_text(encoding=enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detectar_separador(primeira_linha: str) -> str:
    return ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","


def _tratar_bytes_nulos(texto: str, nome_arquivo: str) -> tuple[str, str]:
    """Trata bytes nulos (0x00) encontrados no texto do CSV.

    Padrão real observado: gravação/cópia interrompida deixa um bloco de
    bytes nulos colado ao FINAL do arquivo, depois dos dados válidos. Esse
    padrão é seguro de recuperar automaticamente — descartamos a partir do
    primeiro byte nulo e seguimos com o restante, que contém só dados reais.

    Se os bytes nulos NÃO formarem um bloco final puro (misturados com
    dados, ou sem nenhum conteúdo recuperável antes deles), não é seguro
    adivinhar o que é lixo e o que é dado real — levanta ValueError.
    """
    primeiro_nul = texto.index("\x00")
    cauda = texto[primeiro_nul:]
    texto_limpo = texto[:primeiro_nul].rstrip("\r\n")
    if cauda.strip("\x00\r\n \t") != "" or not texto_limpo.strip():
        raise ValueError(
            f"'{nome_arquivo}' parece corrompido: contém bytes nulos (0x00) misturados "
            "com dados (não apenas no final), então não é seguro recuperar automaticamente. "
            "Reexporte o arquivo original e tente importar novamente."
        )
    aviso = (
        f"'{nome_arquivo}' tinha {len(cauda)} byte(s) nulos (0x00) corrompidos no final "
        "(provavelmente de uma gravação/cópia interrompida). Esse trecho foi descartado "
        "automaticamente e os dados válidos antes dele foram importados normalmente. "
        "Recomenda-se reexportar o arquivo original para confirmar que nada foi perdido."
    )
    return texto_limpo, aviso


def _ler_csv(caminho: Path) -> tuple[list[dict], str | None]:
    """Lê o CSV de alocações. Um arquivo só com cabeçalho (sem linhas de
    dados) é um estado válido — significa simplesmente que ainda não há
    nenhuma alocação registrada (ex.: ao começar a usar a grade real do
    AGHU, antes de qualquer alocação manual).

    Detecta encoding (com/sem BOM) e separador (',' ou ';') automaticamente, e
    normaliza valores ausentes/vazios para "" — uma célula em branco (ou uma
    linha com menos colunas que o cabeçalho) nunca deve travar a importação
    com erro. Retorna (linhas, aviso_corrupcao)."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    encoding = _detectar_encoding(caminho)
    texto = caminho.read_text(encoding=encoding)
    if not texto.strip():
        return [], None

    # CORRIGIDO: arquivo corrompido (gravação/cópia interrompida) pode conter
    # bytes nulos (0x00) — o csv.DictReader explode com "_csv.Error: line
    # contains NUL", exceção que não é ValueError/KeyError e por isso não
    # era tratada em nenhum lugar, derrubando a importação sem mensagem clara.
    # Verificado APÓS o early-return acima para preservar o comportamento de
    # "arquivo vazio é válido" (sem alocações ainda). Quando o bloco nulo é só
    # uma cauda final, recuperamos o prefixo válido — ver _tratar_bytes_nulos.
    aviso_corrupcao: str | None = None
    if "\x00" in texto:
        texto, aviso_corrupcao = _tratar_bytes_nulos(texto, caminho.name)
        # Autocura: grava a versão limpa de volta no arquivo, removendo a
        # cauda de bytes nulos do disco em vez de reprocessá-la para sempre.
        # "utf-8-sig" é o encoding de LEITURA (aceita BOM ou não); se usado
        # para escrita, sempre adiciona um BOM novo mesmo que o arquivo nunca
        # tivesse um. Gravamos como "utf-8" puro para não introduzir BOM.
        encoding_escrita = "utf-8" if encoding == "utf-8-sig" else encoding
        caminho.write_text(texto, encoding=encoding_escrita)

    primeira_linha = texto.splitlines()[0]
    sep = _detectar_separador(primeira_linha)

    reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
    try:
        linhas = [{k: (v.strip() if v else "") for k, v in row.items()} for row in reader]
    except csv.Error as e:
        raise ValueError(f"'{caminho.name}' não pôde ser interpretado como CSV: {e}")
    return linhas, aviso_corrupcao


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
        self.ultimo_aviso: str | None = None
        self.ultimo_linhas_lidas: int = 0
        self._garantir_tabela_alocacoes()

    # ── Interface pública ─────────────────────────────────────────────────────

    def listar_alocacoes(self) -> list[Alocacao]:
        """Retorna alocações CSV sobrescritas pelos ajustes manuais do SQLite,
        incluindo também alocações criadas manualmente que não existem no CSV
        base (ex.: POST /api/alocacoes para uma grade que ainda não tinha
        sala). Sem isso, uma alocação nova só persistia no SQLite mas nunca
        aparecia na listagem, porque o laço original só percorria o CSV."""
        base = self._ler_csv_alocacoes()
        ajustes = {a.id: a for a in self._ler_sqlite_alocacoes()}

        resultado = []
        ids_base = set()
        for aloc in base:
            ids_base.add(aloc.id)
            resultado.append(ajustes.get(aloc.id, aloc))

        for aloc_id, aloc in ajustes.items():
            if aloc_id not in ids_base:
                resultado.append(aloc)

        logger.info("Alocações carregadas: %d registros", len(resultado))
        return resultado

    def buscar_alocacao(self, alocacao_id: str) -> Alocacao | None:
        return next((a for a in self.listar_alocacoes() if a.id == alocacao_id), None)

    def limpar_ajustes(self) -> int:
        """Remove todos os ajustes manuais (alocacoes_ajustes) do SQLite.

        Usado pelo reset de alocações (POST /api/importacao/reset/alocacoes):
        zerar o CSV base não é suficiente, porque ajustes manuais persistidos
        aqui sobrescreveriam qualquer dado novo importado depois, no mesmo id.
        Não toca em historico_ajustes (tabela separada, mantida como registro
        histórico independente do estado atual dos dados).

        Retorna o número de ajustes removidos.
        """
        with sqlite3.connect(self.caminho_db) as conn:
            cursor = conn.execute("DELETE FROM alocacoes_ajustes")
            conn.commit()
            return cursor.rowcount if cursor.rowcount is not None and cursor.rowcount >= 0 else 0

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
        linhas, self.ultimo_aviso = _ler_csv(self.caminho_alocacoes)
        self.ultimo_linhas_lidas = len(linhas)
        if not linhas:
            return []
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho_alocacoes.name)
        alocacoes: list[Alocacao] = []
        for i, linha in enumerate(linhas, start=2):
            try:
                # .get() em vez de [] — uma célula vazia ou ausente no fim da
                # linha não deve travar a importação como erro.
                alocacoes.append(Alocacao(
                    id=linha.get("id", "").strip(),
                    grade_id=linha.get("grade_id", "").strip(),
                    sala_id=linha.get("sala_id", "").strip(),
                    dia_semana=linha.get("dia_semana", "").strip(),
                    turno=linha.get("turno", "").strip(),
                ))
            except (ValueError, KeyError) as e:
                logger.warning("alocacoes.csv linha %d ignorada: %s", i, e)
        alocacoes_validas = [
            a for a in alocacoes
            if a.id and a.grade_id and a.sala_id and a.dia_semana and a.turno
        ]
        descartadas = len(alocacoes) - len(alocacoes_validas)
        if descartadas:
            logger.warning(
                "alocacoes.csv: %d linha(s) ignorada(s) por campos obrigatórios vazios",
                descartadas,
            )
        return alocacoes_validas

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
