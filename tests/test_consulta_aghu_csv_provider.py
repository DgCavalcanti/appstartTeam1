"""Testes do ConsultaAghuCsvProvider — formato real do AGHU (vw_consultas_2026.csv)."""
from __future__ import annotations

import csv
import pytest
from pathlib import Path

from src.repositories.implementations.consulta_aghu_csv_provider import (
    ConsultaAghuCsvProvider,
    _parse_bool_flag,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _escrever_csv(path: Path, linhas: list[dict]) -> None:
    if not linhas:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
        writer.writeheader()
        writer.writerows(linhas)


LINHA_CONSULTA_VALIDA = {
    "Num_Consulta": "C001",
    "Grade": "10001",
    "Profissional": "DR. SILVA",
    "Unidade_Funcional": "AMBULATORIO GERAL",
    "Especialidade": "CARDIOLOGIA",
    "Sigla_Especialidade": "CARDIO",
    "Data_Hora_Consulta": "15/01/2026 08:30:00",
    "Dia_da_Semana": "QUINTA",
    "Turno": "MANHÃ",
    "Situacao_Consulta": "AGENDADO",
    "Condicao_De_Atendimento": "NORMAL",
    "Retorno": "N",
    "Consulta_Excedente": "N",
    "Paciente_Presente": "S",
}


# ── Testes de _parse_bool_flag ────────────────────────────────────────────────

class TestParseBoolFlag:

    @pytest.mark.parametrize("valor,esperado", [
        ("S", True), ("SIM", True), ("TRUE", True), ("1", True), ("T", True),
        ("N", False), ("NAO", False), ("NÃO", False), ("FALSE", False), ("0", False), ("F", False),
        ("", None), ("DESCONHECIDO", None),
    ])
    def test_converte_corretamente(self, valor, esperado):
        assert _parse_bool_flag(valor) == esperado


# ── Testes do provider ────────────────────────────────────────────────────────

class TestConsultaAghuCsvProvider:

    def test_leitura_feliz(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        _escrever_csv(p, [LINHA_CONSULTA_VALIDA])
        provider = ConsultaAghuCsvProvider(caminho=p)
        consultas = provider.listar_consultas()
        assert len(consultas) == 1

    def test_consulta_excedente_convertido_para_bool(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        linha_exc = {**LINHA_CONSULTA_VALIDA, "Consulta_Excedente": "S"}
        _escrever_csv(p, [LINHA_CONSULTA_VALIDA, linha_exc])
        provider = ConsultaAghuCsvProvider(caminho=p)
        consultas = provider.listar_consultas(limit=10)
        excedentes = [c for c in consultas if c.consulta_excedente is True]
        nao_excedentes = [c for c in consultas if c.consulta_excedente is False]
        assert len(excedentes) == 1
        assert len(nao_excedentes) == 1

    def test_arquivo_ausente_lanca_file_not_found(self, tmp_path):
        provider = ConsultaAghuCsvProvider(caminho=tmp_path / "nao_existe.csv")
        with pytest.raises(FileNotFoundError):
            provider.listar_consultas()

    def test_csv_vazio_lanca_value_error(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        p.write_text("", encoding="utf-8")
        provider = ConsultaAghuCsvProvider(caminho=p)
        with pytest.raises(ValueError):
            provider.listar_consultas()

    def test_colunas_obrigatorias_ausentes(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        sem_situacao = {k: v for k, v in LINHA_CONSULTA_VALIDA.items() if k != "Situacao_Consulta"}
        _escrever_csv(p, [sem_situacao])
        provider = ConsultaAghuCsvProvider(caminho=p)
        with pytest.raises(ValueError, match="Situacao_Consulta"):
            provider.listar_consultas()

    def test_paginacao(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        linhas = [{**LINHA_CONSULTA_VALIDA, "Num_Consulta": f"C{i:03d}"} for i in range(10)]
        _escrever_csv(p, linhas)
        provider = ConsultaAghuCsvProvider(caminho=p)
        pagina1 = provider.listar_consultas(limit=4, offset=0)
        pagina2 = provider.listar_consultas(limit=4, offset=4)
        assert len(pagina1) == 4
        assert len(pagina2) == 4

    def test_filtro_apenas_excedentes(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        normal = {**LINHA_CONSULTA_VALIDA, "Num_Consulta": "C001", "Consulta_Excedente": "N"}
        exc    = {**LINHA_CONSULTA_VALIDA, "Num_Consulta": "C002", "Consulta_Excedente": "S"}
        _escrever_csv(p, [normal, exc])
        provider = ConsultaAghuCsvProvider(caminho=p)
        excedentes = provider.listar_consultas(apenas_excedentes=True, limit=100)
        assert len(excedentes) == 1
        assert excedentes[0].consulta_excedente is True

    def test_filtro_especialidade(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        cardio = {**LINHA_CONSULTA_VALIDA, "Num_Consulta": "C001", "Especialidade": "CARDIOLOGIA"}
        ortop  = {**LINHA_CONSULTA_VALIDA, "Num_Consulta": "C002", "Especialidade": "ORTOPEDIA"}
        _escrever_csv(p, [cardio, ortop])
        provider = ConsultaAghuCsvProvider(caminho=p)
        resultado = provider.listar_consultas(especialidade="CARDIO", limit=100)
        assert all("CARDIO" in (c.especialidade or "").upper() for c in resultado)

    def test_data_hora_convertida(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        _escrever_csv(p, [LINHA_CONSULTA_VALIDA])
        provider = ConsultaAghuCsvProvider(caminho=p)
        consultas = provider.listar_consultas()
        # A data deve estar convertida para formato ISO ou mantida
        assert consultas[0].data_hora_consulta is not None

    def test_resumo_importacao(self, tmp_path):
        p = tmp_path / "vw_consultas_2026.csv"
        sem_grade = {**LINHA_CONSULTA_VALIDA, "Num_Consulta": "C002", "Grade": ""}
        _escrever_csv(p, [LINHA_CONSULTA_VALIDA, sem_grade])
        provider = ConsultaAghuCsvProvider(caminho=p)
        r = provider.resumo_importacao()
        assert r["linhas_lidas"] == 2
        assert "sem grade" in " ".join(r["avisos"]).lower()
