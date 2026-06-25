"""Provider para consultas no formato real do AGHU (vw_consultas_2026.csv).

Lê o CSV com segurança para arquivos grandes, normaliza colunas e
converte flags booleanas. Nunca carrega todos os dados no frontend.
"""
from __future__ import annotations

import csv
import io
import logging
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.models.schemas import Consulta

logger = logging.getLogger(__name__)

# Colunas que esperamos no vw_consultas_2026.csv (mínimo)
COLUNAS_OBRIGATORIAS: set[str] = {
    "Situacao_Consulta",
    "Consulta_Excedente",
    "Especialidade",
}

# Algumas exportações reais do AGHU usam nomes de coluna ligeiramente diferentes
# para o mesmo dado. Mapeamos para o nome canônico usado internamente antes de
# qualquer validação/leitura, para que tanto o provider quanto os services que
# leem `linhas brutas` (capacidade_service, qualidade_dados_service) funcionem
# sem precisar conhecer cada variante.
_ALIASES_COLUNAS: dict[str, str] = {
    "Situacao_Da_Consulta": "Situacao_Consulta",
    "Condicao_Do_Atendimento": "Condicao_De_Atendimento",
}

# Mapeamento de nomes de colunas AGHU → nomes internos
_MAPA_COLUNAS: dict[str, str] = {
    "Num_Consulta":          "consulta_id",
    "Num_Consulta_Aghu":     "consulta_id",
    "Grade":                 "grade_id",
    "Profissional":          "profissional",
    "Profissional_Grade":    "profissional",
    "Unidade_Funcional":     "unidade_funcional",
    "Especialidade":         "especialidade",
    "Sigla_Especialidade":   "sigla_especialidade",
    "Data_Hora_Consulta":    "data_hora_consulta",
    "Dt_Hr_Consulta":        "data_hora_consulta",
    "Dia_da_Semana":         "dia_semana",
    "Turno":                 "turno",
    "Situacao_Consulta":     "situacao_consulta",
    "Condicao_De_Atendimento": "condicao_atendimento",
    "Retorno":               "retorno",
    "Consulta_Excedente":    "consulta_excedente",
    "Paciente_Presente":     "paciente_presente",
}

# Situações que representam consulta marcada (agendada)
SITUACOES_MARCADA: frozenset[str] = frozenset({
    "AGENDADO", "AGENDADA", "MARCADO", "MARCADA", "CONFIRMADO", "CONFIRMADA",
    "PRESENTE", "REALIZADO", "REALIZADA",
})
SITUACOES_LIVRE: frozenset[str] = frozenset({"LIVRE", "DISPONIVEL", "DISPONÍVEL"})
SITUACOES_BLOQUEIO: frozenset[str] = frozenset({"BLOQUEADO", "BLOQUEADA", "BLOQUEIO"})


def _detectar_encoding(caminho: Path) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with caminho.open(encoding=enc) as f:
                f.read(4096)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detectar_separador(primeira_linha: str) -> str:
    return ";" if primeira_linha.count(";") > primeira_linha.count(",") else ","


def _normalizar_coluna(nome: str) -> str:
    nome = nome.strip().replace("﻿", "")
    return _ALIASES_COLUNAS.get(nome, nome)


# Caracteres acentuados em UTF-8 (2 bytes, ex.: "ã" = 0xC3 0xA3) que foram
# decodificados erroneamente como CP1252/Latin-1 e depois regravados em UTF-8
# aparecem como pares "Ã" + caractere de continuação (ex.: "ManhÃ£", "AMBULATÃ“RIO").
# Esse fenômeno ("mojibake") é comum em exportações do AGHU feitas em planilhas
# ou ferramentas que não preservam o encoding original.
def _corrigir_mojibake(texto: str) -> str:
    """Repara mojibake de UTF-8 duplamente codificado, quando detectado.

    Faz um round-trip (encode cp1252 -> decode utf-8) no texto inteiro.
    Texto já corretamente codificado em UTF-8 quase sempre falha nesse
    round-trip (bytes inválidos), então a função simplesmente devolve o
    texto original nesse caso — é seguro chamar sempre, mesmo quando não
    há corrupção.
    """
    try:
        corrigido = texto.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto
    return corrigido


def _tratar_bytes_nulos(texto: str, nome_arquivo: str) -> tuple[str, str]:
    """Trata bytes nulos (0x00) encontrados no texto do CSV.

    Padrão real observado: gravação/cópia interrompida deixa um bloco de
    bytes nulos colado ao FINAL do arquivo, depois dos dados válidos (ex.:
    arquivo pré-alocado que nunca terminou de receber o conteúdo). Esse
    padrão é seguro de recuperar automaticamente — descartamos a partir do
    primeiro byte nulo e seguimos com o restante, que contém só dados reais.

    Se os bytes nulos NÃO formarem um bloco final puro (aparecem misturados
    com dados, ou não há nenhum conteúdo recuperável antes deles), não é
    seguro adivinhar o que é lixo e o que é dado real — nesse caso, levanta
    ValueError em vez de arriscar perder informação silenciosamente.
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


def _parse_bool_flag(valor: str) -> Optional[bool]:
    """Converte flags do AGHU em booleano. Retorna None se indeterminado."""
    v = str(valor).strip().upper()
    if v in ("S", "SIM", "TRUE", "1", "T"):
        return True
    if v in ("N", "NAO", "NÃO", "FALSE", "0", "F"):
        return False
    return None


def _parse_data(valor: str) -> Optional[str]:
    """Tenta converter a data para ISO 8601. Retorna a string original em caso de falha."""
    if not valor:
        return None
    formatos = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    for fmt in formatos:
        try:
            return datetime.strptime(valor.strip(), fmt).isoformat()
        except ValueError:
            continue
    return valor.strip() or None


def _mapear_linha(linha: dict[str, str]) -> dict:
    """Aplica o mapeamento de colunas AGHU → campos internos."""
    resultado: dict = {}
    for col_aghu, col_interna in _MAPA_COLUNAS.items():
        if col_aghu in linha and col_interna not in resultado:
            resultado[col_interna] = linha[col_aghu]
    # Campos booleanos
    for campo in ("retorno", "consulta_excedente", "paciente_presente"):
        if campo in resultado:
            resultado[campo] = _parse_bool_flag(resultado[campo])
    # Data/hora
    if "data_hora_consulta" in resultado:
        resultado["data_hora_consulta"] = _parse_data(resultado["data_hora_consulta"])
    return resultado


def _normalizar_busca(texto: str) -> str:
    """Remove acentos/diacríticos e normaliza para maiúsculas.

    CORRIGIDO (auditoria técnica): a busca por especialidade (e demais
    campos textuais) comparava apenas em maiúsculas (`.upper()`), então
    buscar "obstetricia" (sem acento) não encontrava "Obstetrícia" no CSV.
    Usando NFKD + remoção dos caracteres combinantes (acentos), a busca
    passa a ignorar tanto caixa quanto acentuação nos dois lados da
    comparação (termo buscado e valor do CSV).
    """
    sem_acento = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in sem_acento if not unicodedata.combining(c))
    return sem_acento.strip().upper()


def _situacao_normalizada(situacao: str) -> str:
    return _normalizar_busca(situacao)


class ConsultaAghuCsvProvider:
    """Lê vw_consultas_2026.csv e oferece acesso paginado e agregado."""

    def __init__(self, caminho: Path = Path("data/vw_consultas_2026.csv")) -> None:
        self.caminho = caminho
        self._cache: list[dict] | None = None  # cache das linhas brutas normalizadas
        self._aviso_corrupcao: str | None = None  # aviso de cauda nula descartada, se houver

    # ── Leitura base ──────────────────────────────────────────────────────────

    def _carregar(self) -> list[dict]:
        """Carrega e normaliza o CSV inteiro na memória (uma única vez)."""
        if self._cache is not None:
            return self._cache

        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.caminho}")

        encoding = _detectar_encoding(self.caminho)
        texto = self.caminho.read_text(encoding=encoding)

        # CORRIGIDO: um arquivo corrompido (ex.: gravação interrompida, cópia
        # truncada) pode ficar com um grande trecho de bytes nulos (0x00) após
        # os dados reais — o tamanho do arquivo no disco fica enorme, mas o
        # conteúdo válido é só o início. Sem essa checagem, o código seguia
        # tentando processar o arquivo inteiro (round-trip de mojibake +
        # parsing CSV) e acabava estourando em "_csv.Error: line contains
        # NUL", uma exceção que não é ValueError/KeyError e por isso não era
        # tratada em nenhum lugar — toda requisição que dependesse de
        # consultas voltava a refazer esse trabalho pesado (sem cache, já que
        # a leitura nunca chegava a ter sucesso) e travava/derrubava o app.
        # Verificamos isso ANTES do round-trip de mojibake para falhar rápido
        # em vez de gastar tempo/memória processando bytes inválidos. Quando o
        # bloco nulo é só uma cauda final (caso comum), recuperamos o prefixo
        # válido em vez de rejeitar o arquivo inteiro — ver _tratar_bytes_nulos.
        if "\x00" in texto:
            texto, self._aviso_corrupcao = _tratar_bytes_nulos(texto, self.caminho.name)
            # Autocura: grava a versão limpa de volta no arquivo, removendo a
            # cauda de bytes nulos do disco. Sem isso, o arquivo continuaria
            # gigante/corrompido para sempre e cada leitura reprocessaria o
            # mesmo truncamento — exatamente o desperdício identificado na
            # auditoria original (sem ganho de cache, reprocessamento caro
            # repetido). No fluxo de importação, `self.caminho` é o arquivo
            # temporário ainda não publicado, então isso limpa o arquivo
            # antes mesmo dele se tornar o arquivo ativo.
            # NOTA: "utf-8-sig" é o encoding de LEITURA (aceita BOM ou não);
            # se usado para escrita, sempre adiciona um BOM novo, mesmo que o
            # arquivo original nunca tivesse um. Por isso gravamos sempre como
            # "utf-8" puro (texto já vem sem BOM, pois o decode utf-8-sig o
            # remove) — evita introduzir um BOM espúrio durante a autocura.
            encoding_escrita = "utf-8" if encoding == "utf-8-sig" else encoding
            self.caminho.write_text(texto, encoding=encoding_escrita)

        texto = _corrigir_mojibake(texto)

        if not texto.strip():
            raise ValueError(f"Arquivo CSV vazio: {self.caminho}")

        primeira_linha = texto.splitlines()[0]
        sep = _detectar_separador(primeira_linha)

        reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
        linhas = []
        try:
            for row in reader:
                linha_norm = {_normalizar_coluna(k): (v.strip() if v else "") for k, v in row.items()}
                linhas.append(linha_norm)
        except csv.Error as e:
            # Rede de segurança: qualquer outro problema estrutural do CSV
            # (ex.: aspas não fechadas) também deve virar um erro tratável em
            # vez de subir cru e derrubar a requisição.
            raise ValueError(f"'{self.caminho.name}' não pôde ser interpretado como CSV: {e}")

        # CORRIGIDO: cabeçalho presente mas 0 linhas de dados é um estado
        # válido (ex.: arquivo recém-resetado via
        # /api/importacao/reset/consultas, antes de uma nova importação) —
        # não só "arquivo corrompido/vazio". Erro real de arquivo sem nem
        # cabeçalho já foi pego acima por `if not texto.strip()`. Sem linhas,
        # não há nada a validar contra COLUNAS_OBRIGATORIAS.
        if linhas:
            self._validar_colunas(linhas)

        logger.info(
            "%s carregado: %d linhas (encoding=%s, sep='%s')",
            self.caminho.name, len(linhas), encoding, sep,
        )
        self._cache = linhas
        return linhas

    def _validar_colunas(self, linhas: list[dict]) -> None:
        presentes = set(linhas[0].keys())
        ausentes = COLUNAS_OBRIGATORIAS - presentes
        if ausentes:
            raise ValueError(
                f"'{self.caminho.name}' está faltando colunas obrigatórias: {sorted(ausentes)}. "
                f"Colunas presentes: {sorted(presentes)}"
            )

    def _linha_para_consulta(self, linha: dict) -> Consulta:
        mapeado = _mapear_linha(linha)
        return Consulta(**{k: v for k, v in mapeado.items() if k in Consulta.model_fields})

    # ── API pública ───────────────────────────────────────────────────────────

    def listar_consultas(
        self,
        limit: int = 100,
        offset: int = 0,
        especialidade: str | None = None,
        unidade_funcional: str | None = None,
        profissional: str | None = None,
        turno: str | None = None,
        dia_semana: str | None = None,
        situacao_consulta: str | None = None,
        apenas_excedentes: bool = False,
    ) -> list[Consulta]:
        linhas = self._carregar()

        filtradas = []
        for linha in linhas:
            # CORRIGIDO (auditoria técnica): comparações abaixo usam
            # _normalizar_busca() (ignora maiúsculas/minúsculas E acentos)
            # em vez de .upper() puro, para que "cardiologia", "CARDIOLOGIA"
            # e "Cardiología" encontrem o mesmo resultado.
            if especialidade and _normalizar_busca(especialidade) not in _normalizar_busca(linha.get("Especialidade", "")):
                continue
            if unidade_funcional and _normalizar_busca(unidade_funcional) not in _normalizar_busca(linha.get("Unidade_Funcional", "")):
                continue
            if profissional and _normalizar_busca(profissional) not in _normalizar_busca(linha.get("Profissional", "") or linha.get("Profissional_Grade", "")):
                continue
            if turno and _normalizar_busca(turno) not in _normalizar_busca(linha.get("Turno", "")):
                continue
            if dia_semana and _normalizar_busca(dia_semana) not in _normalizar_busca(linha.get("Dia_da_Semana", "")):
                continue
            if situacao_consulta:
                sit = _situacao_normalizada(linha.get("Situacao_Consulta", ""))
                if _normalizar_busca(situacao_consulta) not in sit:
                    continue
            if apenas_excedentes and _parse_bool_flag(linha.get("Consulta_Excedente", "")) is not True:
                continue
            filtradas.append(linha)

        pagina = filtradas[offset: offset + limit]
        return [self._linha_para_consulta(linha) for linha in pagina]

    def total_filtrado(
        self,
        especialidade: str | None = None,
        situacao_consulta: str | None = None,
        apenas_excedentes: bool = False,
    ) -> int:
        return len(self.listar_consultas(
            limit=10_000_000,
            especialidade=especialidade,
            situacao_consulta=situacao_consulta,
            apenas_excedentes=apenas_excedentes,
        ))

    def listar_linhas_brutas(self) -> list[dict]:
        """Retorna as linhas normalizadas brutas (para uso interno pelos services)."""
        return self._carregar()

    def resumo_importacao(self) -> dict:
        linhas = self._carregar()
        total = len(linhas)
        excedentes = sum(
            1 for linha in linhas if _parse_bool_flag(linha.get("Consulta_Excedente", "")) is True
        )
        sem_data = sum(1 for linha in linhas if not linha.get("Data_Hora_Consulta") and not linha.get("Dt_Hr_Consulta"))
        sem_grade = sum(1 for linha in linhas if not linha.get("Grade"))

        avisos = []
        if self._aviso_corrupcao:
            avisos.append(self._aviso_corrupcao)
        if sem_data:
            avisos.append(f"Existem {sem_data} consultas sem data/hora")
        if sem_grade:
            avisos.append(f"Existem {sem_grade} consultas sem grade associada")

        return {
            "arquivo": self.caminho.name,
            "linhas_lidas": total,
            "linhas_validas": total,
            "registros_unicos": total,
            "excedentes": excedentes,
            "avisos": avisos,
        }
