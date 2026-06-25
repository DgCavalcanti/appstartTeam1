"""Testes do AlocacaoSaaCsvProvider."""
from __future__ import annotations

import csv
from pathlib import Path

from src.providers.implementations.alocacao_saa_csv_provider import AlocacaoSaaCsvProvider


def _escrever_csv(path: Path, linhas: list[dict], sep: str = ";") -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "grade_id", "sala_id", "dia_semana", "turno"],
            delimiter=sep,
        )
        writer.writeheader()
        writer.writerows(linhas)


def test_ignora_alocacoes_com_campos_obrigatorios_vazios(tmp_path):
    csv_path = tmp_path / "alocacoes.csv"
    db_path = tmp_path / "saa.db"
    _escrever_csv(csv_path, [
        {"id": "A001", "grade_id": "", "sala_id": "S001", "dia_semana": "", "turno": ""},
        {"id": "A002", "grade_id": "G002", "sala_id": "S002", "dia_semana": "Segunda", "turno": "Manha"},
    ])

    provider = AlocacaoSaaCsvProvider(caminho_alocacoes=csv_path, caminho_db=db_path)
    alocacoes = provider.listar_alocacoes()

    assert provider.ultimo_linhas_lidas == 2
    assert len(alocacoes) == 1
    assert alocacoes[0].id == "A002"

