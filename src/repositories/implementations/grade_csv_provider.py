"""Provider CSV para grades — lê grades.csv e valida o contrato MVP."""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from src.models.schemas import Grade
from src.repositories.interfaces.grade_provider_interface import GradeProviderInterface

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = {"id", "especialidade", "profissional", "dia_semana", "turno", "qtd_salas_necessarias"}


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


class GradeCsvProvider(GradeProviderInterface):

    def __init__(self, caminho: Path = Path("data/grades.csv")) -> None:
        self.caminho = caminho

    def listar_grades(self) -> list[Grade]:
        linhas = _ler_csv(self.caminho)
        _validar_colunas(linhas, COLUNAS_OBRIGATORIAS, self.caminho.name)

        grades: list[Grade] = []
        erros: list[str] = []

        for i, linha in enumerate(linhas, start=2):
            try:
                grades.append(Grade(
                    id=linha["id"].strip(),
                    especialidade=linha["especialidade"].strip(),
                    profissional=linha["profissional"].strip(),
                    dia_semana=linha["dia_semana"].strip(),
                    turno=linha["turno"].strip(),
                    qtd_salas_necessarias=int(linha["qtd_salas_necessarias"]),
                ))
            except (ValueError, KeyError) as e:
                erros.append(f"Linha {i}: {e}")

        if erros:
            raise ValueError(f"grades.csv contém {len(erros)} linha(s) inválida(s): {erros}")

        logger.info("grades.csv carregado: %d registros", len(grades))
        return grades

    def buscar_grade(self, grade_id: str) -> Grade | None:
        return next((g for g in self.listar_grades() if g.id == grade_id), None)
