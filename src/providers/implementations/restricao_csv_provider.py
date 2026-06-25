"""Provider CSV para restrições — lê restricoes.csv e valida o contrato MVP."""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from src.models.schemas import Restricao
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "sala_id", "tipo", "valor"}


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
    """Detecta encoding (com/sem BOM) e separador (',' ou ';') automaticamente,
    e normaliza valores ausentes/vazios para "" — uma célula em branco nunca
    deve travar a importação com erro (mesmo padrão usado em sala_csv_provider
    e nos providers AGHU). Retorna (linhas, aviso_corrupcao)."""
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    encoding = _detectar_encoding(caminho)
    texto = caminho.read_text(encoding=encoding)
    if not texto.strip():
        raise ValueError(f"Arquivo CSV vazio: {caminho}")

    # CORRIGIDO: arquivo corrompido (gravação/cópia interrompida) pode conter
    # bytes nulos (0x00) — o csv.DictReader explode com "_csv.Error: line
    # contains NUL", exceção que não é ValueError/KeyError e por isso não
    # era tratada em nenhum lugar, derrubando a importação sem mensagem clara.
    # Quando o bloco nulo é só uma cauda final, recuperamos o prefixo válido
    # em vez de rejeitar o arquivo inteiro — ver _tratar_bytes_nulos.
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
    # CORRIGIDO: cabeçalho presente mas 0 linhas de dados é um estado válido
    # (ex.: arquivo recém-resetado via /api/importacao/reset/restricoes, antes
    # de uma nova importação) — não só "arquivo corrompido/vazio". Erro real
    # de arquivo sem nem cabeçalho já foi pego acima por `if not texto.strip()`.
    return linhas, aviso_corrupcao


def _validar_colunas(linhas: list[dict], obrigatorias: set[str], nome: str) -> None:
    ausentes = obrigatorias - set(linhas[0].keys())
    if ausentes:
        raise ValueError(f"'{nome}' está faltando colunas obrigatórias: {sorted(ausentes)}")


class RestricaoCsvProvider(RestricaoProviderInterface):

    def __init__(self, caminho: Path = Path("data/restricoes.csv")) -> None:
        self.caminho = caminho
        self.ultimo_aviso: str | None = None

    def listar_restricoes(self) -> list[Restricao]:
        linhas, self.ultimo_aviso = _ler_csv(self.caminho)
        if not linhas:
            return []
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho.name)

        restricoes: list[Restricao] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                restricoes.append(Restricao(
                    id=linha.get("id", "").strip(),
                    sala_id=linha.get("sala_id", "").strip(),
                    tipo=linha.get("tipo", "").strip(),
                    valor=linha.get("valor", "").strip(),
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            raise ValueError(f"restricoes.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("restricoes.csv carregado: %d registros", len(restricoes))
        return restricoes
