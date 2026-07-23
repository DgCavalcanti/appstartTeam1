"""Provider para consultas no formato real do AGHU (vw_consultas_2026.csv).

Lê o CSV com segurança para arquivos grandes, normaliza colunas e
converte flags booleanas. Nunca carrega todos os dados no frontend.
"""
from __future__ import annotations

import csv
import io
import logging
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


def _situacao_normalizada(situacao: str) -> str:
    return situacao.strip().upper().replace("Ç", "C").replace("Ã", "A")


class ConsultaAghuCsvProvider:
    """Lê vw_consultas_2026.csv e oferece acesso paginado e agregado."""

    def __init__(self, caminho: Path = Path("data/vw_consultas_2026.csv")) -> None:
        self.caminho = caminho
        self._cache: list[dict] | None = None  # cache das linhas brutas normalizadas

    # ── Leitura base ──────────────────────────────────────────────────────────

    def _carregar(self) -> list[dict]:
        """Carrega e normaliza o CSV inteiro na memória (uma única vez)."""
        if self._cache is not None:
            return self._cache

        if not self.caminho.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {self.caminho}")

        encoding = _detectar_encoding(self.caminho)
        texto = self.caminho.read_text(encoding=encoding)
        texto = _corrigir_mojibake(texto)

        if not texto.strip():
            raise ValueError(f"Arquivo CSV vazio: {self.caminho}")

        primeira_linha = texto.splitlines()[0]
        sep = _detectar_separador(primeira_linha)

        reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
        linhas = []
        for row in reader:
            linha_norm = {_normalizar_coluna(k): (v.strip() if v else "") for k, v in row.items()}
            linhas.append(linha_norm)

        if not linhas:
            raise ValueError(f"Arquivo CSV sem linhas de dados: {self.caminho}")

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
            if especialidade and especialidade.upper() not in linha.get("Especialidade", "").upper():
                continue
            if unidade_funcional and unidade_funcional.upper() not in linha.get("Unidade_Funcional", "").upper():
                continue
            if profissional and profissional.upper() not in (linha.get("Profissional", "") or linha.get("Profissional_Grade", "")).upper():
                continue
            if turno and turno.upper() not in linha.get("Turno", "").upper():
                continue
            if dia_semana and dia_semana.upper() not in linha.get("Dia_da_Semana", "").upper():
                continue
            if situacao_consulta:
                sit = _situacao_normalizada(linha.get("Situacao_Consulta", ""))
                if situacao_consulta.upper() not in sit:
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
