"""Provider CSV para salas — lê salas.csv e valida o contrato MVP."""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

from src.models.schemas import Sala
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface

logger = logging.getLogger(__name__)

# CORRIGIDO: apenas id/numero/bloco/status são de fato obrigatórios — andar,
# acessibilidade e equipamentos são opcionais (como a própria tela de
# importação já informa: "Opcionais: andar, acessibilidade, equipamentos...").
# Antes os 7 campos estavam marcados como obrigatórios, então um salas.csv
# sem alguma coluna opcional já era rejeitado como inválido.
COLUNAS_OBRIGATORIAS = {"id", "numero", "bloco", "status"}


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
    """Lê o CSV com detecção automática de encoding (com/sem BOM) e separador
    (',' ou ';' — exportações do Excel em pt-BR costumam usar ';'). Sem isso,
    um arquivo com ';' era lido como uma única coluna gigante, fazendo todas
    as colunas (inclusive as obrigatórias) aparecerem como "ausentes".

    Valores ausentes ou vazios são normalizados para string vazia — uma
    célula em branco (ou uma linha com menos colunas que o cabeçalho) nunca
    deve travar a importação com erro.

    Retorna (linhas, aviso_corrupcao).
    """
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
    # (ex.: arquivo recém-resetado via /api/importacao/reset/salas, antes de
    # uma nova importação) — não só "arquivo corrompido/vazio". Erro real de
    # arquivo sem nem cabeçalho já foi pego acima por `if not texto.strip()`.
    return linhas, aviso_corrupcao


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
        self.ultimo_aviso: str | None = None

    def listar_salas(self) -> list[Sala]:
        linhas, self.ultimo_aviso = _ler_csv(self.caminho)
        if not linhas:
            # Dataset vazio (cabeçalho sem linhas de dados) é válido — não há
            # cabeçalho concreto para validar colunas contra, então não há
            # nada a checar. Ver nota em _ler_csv.
            return []
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho.name)

        salas: list[Sala] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                # CORRIGIDO: andar/acessibilidade/equipamentos/especialidade_preferencial
                # são opcionais — usar .get() em vez de [] evita KeyError quando a
                # coluna não existe no arquivo, e o valor vira "" (ou False/[] após
                # o parse), em vez de travar a importação.
                esp_pref = linha.get("especialidade_preferencial", "").strip() or None
                salas.append(Sala(
                    id=linha.get("id", "").strip(),
                    numero=linha.get("numero", "").strip(),
                    bloco=linha.get("bloco", "").strip(),
                    andar=linha.get("andar", "").strip(),
                    status=linha.get("status", "").strip(),
                    acessibilidade=_parse_bool(linha.get("acessibilidade", "")),
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
