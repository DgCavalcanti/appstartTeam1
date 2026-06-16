"""Testes do SalaCsvProvider."""
from __future__ import annotations

import csv
import pytest
from pathlib import Path

from src.providers.implementations.sala_csv_provider import SalaCsvProvider


def _escrever_csv(path: Path, linhas: list[dict]) -> None:
    if not linhas:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


LINHA_VALIDA = {
    "id": "S001",
    "numero": "101",
    "bloco": "A",
    "andar": "1",
    "status": "disponivel",
    "acessibilidade": "true",
    "equipamentos": "ECG;Monitor",
    "especialidade_preferencial": "Cardiologia",
}


class TestSalaCsvProvider:

    def test_leitura_feliz(self, tmp_path):
        p = tmp_path / "salas.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = SalaCsvProvider(caminho=p)
        salas = provider.listar_salas()
        assert len(salas) == 1
        assert salas[0].id == "S001"
        assert salas[0].acessibilidade is True
        assert salas[0].equipamentos == ["ECG", "Monitor"]

    def test_equipamentos_vazios(self, tmp_path):
        p = tmp_path / "salas.csv"
        linha = {**LINHA_VALIDA, "equipamentos": ""}
        _escrever_csv(p, [linha])
        provider = SalaCsvProvider(caminho=p)
        sala = provider.listar_salas()[0]
        assert sala.equipamentos == []

    def test_acessibilidade_false(self, tmp_path):
        p = tmp_path / "salas.csv"
        linha = {**LINHA_VALIDA, "acessibilidade": "false"}
        _escrever_csv(p, [linha])
        provider = SalaCsvProvider(caminho=p)
        assert provider.listar_salas()[0].acessibilidade is False

    def test_especialidade_preferencial_vazia_vira_none(self, tmp_path):
        p = tmp_path / "salas.csv"
        linha = {**LINHA_VALIDA, "especialidade_preferencial": ""}
        _escrever_csv(p, [linha])
        provider = SalaCsvProvider(caminho=p)
        assert provider.listar_salas()[0].especialidade_preferencial is None

    def test_ids_sao_string(self, tmp_path):
        p = tmp_path / "salas.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = SalaCsvProvider(caminho=p)
        assert isinstance(provider.listar_salas()[0].id, str)

    def test_arquivo_ausente_lanca_file_not_found(self, tmp_path):
        provider = SalaCsvProvider(caminho=tmp_path / "nao_existe.csv")
        with pytest.raises(FileNotFoundError):
            provider.listar_salas()

    def test_coluna_obrigatoria_ausente_lanca_value_error(self, tmp_path):
        p = tmp_path / "salas.csv"
        linha = {k: v for k, v in LINHA_VALIDA.items() if k != "status"}
        _escrever_csv(p, [linha])
        provider = SalaCsvProvider(caminho=p)
        with pytest.raises(ValueError, match="status"):
            provider.listar_salas()

    def test_buscar_sala_existente(self, tmp_path):
        p = tmp_path / "salas.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = SalaCsvProvider(caminho=p)
        sala = provider.buscar_sala("S001")
        assert sala is not None

    def test_buscar_sala_inexistente(self, tmp_path):
        p = tmp_path / "salas.csv"
        _escrever_csv(p, [LINHA_VALIDA])
        provider = SalaCsvProvider(caminho=p)
        assert provider.buscar_sala("XPTO") is None
