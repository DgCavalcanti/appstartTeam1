"""Provider para grades no formato real do AGHU (vw_grades.csv).

Regra crítica: Quantidade_Vagas representa capacidade de atendimento/vagas,
NÃO o número de salas físicas. No MVP, qtd_salas_necessarias = 1 por grade.
"""
from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Literal

from src.models.schemas import GradeAghu

logger = logging.getLogger(__name__)

# Colunas que o arquivo AGHU real deve conter
COLUNAS_OBRIGATORIAS_AGHU: set[str] = {
    "Grade",
    "Profissional_Grade",
    "Unidade_Funcional",
    "Condicao_De_Atendimento",
    "Especialidade",
    "Situacao_Atual_Grade",
    "Dia_da_Semana",
    "Turno",
    "Situacao_Atual_Horario",
    "Quantidade_Vagas",
}

# Colunas do formato simplificado antigo (para detecção de tipo)
COLUNAS_FORMATO_SIMPLES: set[str] = {
    "id", "especialidade", "profissional", "dia_semana", "turno", "qtd_salas_necessarias"
}


def detect_csv_type(
    headers: list[str],
) -> Literal["grade_simplificada", "grade_aghu", "consulta_aghu", "desconhecido"]:
    """Detecta o tipo de CSV a partir dos cabeçalhos normalizados."""
    h = {c.strip() for c in headers}
    if COLUNAS_FORMATO_SIMPLES.issubset(h):
        return "grade_simplificada"
    if {"Grade", "Profissional_Grade", "Quantidade_Vagas"}.issubset(h):
        return "grade_aghu"
    if {"Situacao_Consulta", "Consulta_Excedente"}.issubset(h) or {
        "situacao_consulta", "consulta_excedente"
    }.issubset({c.lower() for c in h}):
        return "consulta_aghu"
    return "desconhecido"


def _detectar_encoding(caminho: Path) -> str:
    """Tenta utf-8-sig (BOM) primeiro; cai para latin-1 em caso de falha."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            caminho.read_text(encoding=enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _corrigir_mojibake(texto: str) -> str:
    """Repara mojibake de UTF-8 duplamente codificado (ex.: "ManhÃ£" -> "Manhã").

    Faz um round-trip (encode cp1252 -> decode utf-8). Texto já corretamente
    codificado em UTF-8 quase sempre falha nesse round-trip (bytes inválidos),
    então a função devolve o texto original nesse caso — é seguro chamar
    sempre, mesmo quando o arquivo não está corrompido.
    """
    try:
        return texto.encode("cp1252").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return texto


def _detectar_separador(linha: str) -> str:
    return ";" if linha.count(";") > linha.count(",") else ","


def _normalizar_nome_coluna(nome: str) -> str:
    return nome.strip().replace("﻿", "")


def _ler_csv_aghu(caminho: Path) -> tuple[list[dict], str]:
    """Lê o CSV com detecção automática de encoding e separador.

    Retorna (linhas, encoding_usado).
    """
    if not caminho.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {caminho}")

    encoding = _detectar_encoding(caminho)
    texto = caminho.read_text(encoding=encoding)
    texto = _corrigir_mojibake(texto)

    if not texto.strip():
        raise ValueError(f"Arquivo CSV vazio: {caminho}")

    primeira_linha = texto.splitlines()[0]
    sep = _detectar_separador(primeira_linha)

    reader = csv.DictReader(io.StringIO(texto), delimiter=sep)
    linhas = []
    for row in reader:
        # normaliza nomes de colunas (remove espaços, BOM)
        linha_norm = {_normalizar_nome_coluna(k): (v.strip() if v else "") for k, v in row.items()}
        linhas.append(linha_norm)

    if not linhas:
        raise ValueError(f"Arquivo CSV sem linhas de dados: {caminho}")

    return linhas, encoding


def _validar_colunas(linhas: list[dict], obrigatorias: set[str], nome_arquivo: str) -> None:
    presentes = set(linhas[0].keys())
    ausentes = obrigatorias - presentes
    if ausentes:
        raise ValueError(
            f"'{nome_arquivo}' está faltando colunas obrigatórias: {sorted(ausentes)}. "
            f"Colunas presentes: {sorted(presentes)}"
        )


def _parse_int_seguro(valor: str, padrao: int = 0) -> int:
    try:
        return int(str(valor).strip())
    except (ValueError, TypeError):
        return padrao


class GradeAghuCsvProvider:
    """Lê vw_grades.csv no formato real do AGHU e retorna objetos GradeAghu."""

    def __init__(self, caminho: Path = Path("data/vw_grades.csv")) -> None:
        self.caminho = caminho

    def listar_grades(self) -> list[GradeAghu]:
        linhas, encoding = _ler_csv_aghu(self.caminho)
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS_AGHU, self.caminho.name)

        grades: list[GradeAghu] = []
        avisos: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                # grade_id: preserva como string, inclusive zeros à esquerda
                grade_id = str(linha.get("Grade", "")).strip()
                if not grade_id:
                    avisos.append(f"Linha {i}: campo 'Grade' vazio — ignorada")
                    continue

                quantidade_vagas = _parse_int_seguro(linha.get("Quantidade_Vagas", "0"))

                grades.append(GradeAghu(
                    grade_id=grade_id,
                    profissional=linha.get("Profissional_Grade", "").strip(),
                    unidade_funcional=linha.get("Unidade_Funcional", "").strip(),
                    condicao_atendimento=linha.get("Condicao_De_Atendimento", "").strip(),
                    especialidade=linha.get("Especialidade", "").strip(),
                    situacao_grade=linha.get("Situacao_Atual_Grade", "").strip(),
                    dia_semana=linha.get("Dia_da_Semana", "").strip(),
                    hora_inicio=linha.get("Hora_Inicio", "").strip() or None,
                    turno=linha.get("Turno", "").strip(),
                    situacao_horario=linha.get("Situacao_Atual_Horario", "").strip(),
                    quantidade_vagas=quantidade_vagas,
                    qtd_salas_necessarias=1,  # regra MVP: 1 sala por grade/horário
                ))
            except Exception as e:
                avisos.append(f"Linha {i}: {e}")

        if avisos:
            logger.warning(
                "%s: %d aviso(s) durante leitura:\n%s",
                self.caminho.name,
                len(avisos),
                "\n".join(avisos[:20]),
            )

        logger.info(
            "%s carregado: %d registros (encoding=%s)",
            self.caminho.name, len(grades), encoding,
        )
        return grades

    def buscar_grade(self, grade_id: str) -> GradeAghu | None:
        return next((g for g in self.listar_grades() if g.grade_id == grade_id), None)

    def resumo_importacao(self) -> dict:
        """Retorna estatísticas de qualidade da importação."""
        linhas, _ = _ler_csv_aghu(self.caminho)
        grades = self.listar_grades()

        sem_dia = sum(1 for g in grades if not g.dia_semana)
        sem_hora = sum(1 for g in grades if not g.hora_inicio)
        sem_turno = sum(1 for g in grades if not g.turno)
        grades_unicas = len({g.grade_id for g in grades})

        avisos = []
        if sem_dia:
            avisos.append(f"Existem {sem_dia} linhas sem dia da semana")
        if sem_hora:
            avisos.append(f"Existem {sem_hora} linhas sem hora de início")
        if sem_turno:
            avisos.append(f"Existem {sem_turno} linhas sem turno")

        return {
            "arquivo": self.caminho.name,
            "linhas_lidas": len(linhas),
            "linhas_validas": len(grades),
            "grades_unicas": grades_unicas,
            "avisos": avisos,
        }
