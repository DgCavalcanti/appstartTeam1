"""Testes do GradeCsvProvider."""
from __future__ import annotations

import csv
import pytest
from pathlib import Path

from src.repositories.implementations.grade_csv_provider import GradeCsvProvider


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _escrever_csv(path: Path, linhas: list[dict]) -> None:
    if not linhas:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


LINHA_VALIDA = {
    "id": "G001",
    "especialidade": "Ortopedia",
    "profissional": "Dr. Souza",
    "dia_semana": "Segunda",
    "turno": "Manhã",
    "qtd_salas_necessarias": "2",
}


# ── Testes ───────────────────────────────────────────────────────────────────

class TestGradeCsvProvider:

    def test_leitura_feliz(self, tmp_path):
        p = tmp_path / "grades.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = GradeCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 1
        assert grades[0].id == "G001"
        assert grades[0].especialidade == "Ortopedia"
        assert grades[0].qtd_salas_necessarias == 2

    def test_arquivo_ausente_lanca_file_not_found(self, tmp_path):
        provider = GradeCsvProvider(caminho=tmp_path / "nao_existe.csv")
        with pytest.raises(FileNotFoundError):
            provider.listar_grades()

    def test_csv_vazio_lanca_value_error(self, tmp_path):
        p = tmp_path / "grades.csv"
        p.write_text("", encoding="utf-8")
        provider = GradeCsvProvider(caminho=p)
        with pytest.raises(ValueError, match="vazio"):
            provider.listar_grades()

    def test_coluna_ausente_lanca_value_error(self, tmp_path):
        p = tmp_path / "grades.csv"
        linha_incompleta = {k: v for k, v in LINHA_VALIDA.items() if k != "turno"}
        _escrever_csv(p, [linha_incompleta])
        provider = GradeCsvProvider(caminho=p)
        with pytest.raises(ValueError, match="turno"):
            provider.listar_grades()

    def test_ids_sao_string(self, tmp_path):
        p = tmp_path / "grades.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = GradeCsvProvider(caminho=p)
        grade = provider.listar_grades()[0]
        assert isinstance(grade.id, str)

    def test_buscar_grade_existente(self, tmp_path):
        p = tmp_path / "grades.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = GradeCsvProvider(caminho=p)
        grade = provider.buscar_grade("G001")
        assert grade is not None
        assert grade.id == "G001"

    def test_buscar_grade_inexistente_retorna_none(self, tmp_path):
        p = tmp_path / "grades.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = GradeCsvProvider(caminho=p)
        assert provider.buscar_grade("XPTO") is None

    def test_multiples_grades(self, tmp_path):
        p = tmp_path / "grades.csv"
        linha2 = {**LINHA_VALIDA, "id": "G002", "especialidade": "Cardiologia"}
        _escrever_csv(p, [LINHA_VALIDA, linha2])
        provider = GradeCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 2
