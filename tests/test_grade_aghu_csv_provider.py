"""Testes do GradeAghuCsvProvider — formato real do AGHU (vw_grades.csv)."""
from __future__ import annotations

import csv
import pytest
from pathlib import Path

from src.repositories.implementations.grade_aghu_csv_provider import (
    GradeAghuCsvProvider,
    detect_csv_type,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _escrever_csv(path: Path, linhas: list[dict], sep: str = ",") -> None:
    if not linhas:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(linhas[0].keys()), delimiter=sep)
        writer.writeheader()
        writer.writerows(linhas)


LINHA_AGHU_VALIDA = {
    "Grade": "10001",
    "Profissional_Grade": "DR. SILVA",
    "Unidade_Funcional": "AMBULATORIO GERAL",
    "Condicao_De_Atendimento": "NORMAL",
    "Especialidade": "CARDIOLOGIA",
    "Situacao_Atual_Grade": "ATIVO",
    "Dia_da_Semana": "SEGUNDA",
    "Hora_Inicio": "08:00",
    "Turno": "MANHÃ",
    "Situacao_Atual_Horario": "ATIVO",
    "Quantidade_Vagas": "12",
}

LINHA_SIMPLES = {
    "id": "G001",
    "especialidade": "Ortopedia",
    "profissional": "Dr. Souza",
    "dia_semana": "Segunda",
    "turno": "Manhã",
    "qtd_salas_necessarias": "2",
}


# ── Testes de detecção de tipo ────────────────────────────────────────────────

class TestDetectCsvType:

    def test_detecta_grade_aghu(self):
        headers = list(LINHA_AGHU_VALIDA.keys())
        assert detect_csv_type(headers) == "grade_aghu"

    def test_detecta_grade_simplificada(self):
        headers = list(LINHA_SIMPLES.keys())
        assert detect_csv_type(headers) == "grade_simplificada"

    def test_desconhecido(self):
        assert detect_csv_type(["col1", "col2"]) == "desconhecido"


# ── Testes de leitura ─────────────────────────────────────────────────────────

class TestGradeAghuCsvProvider:

    def test_leitura_feliz(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA])
        provider = GradeAghuCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 1
        g = grades[0]
        assert g.grade_id == "10001"
        assert g.especialidade == "CARDIOLOGIA"
        assert g.profissional == "DR. SILVA"

    def test_grade_id_preservado_como_string(self, tmp_path):
        """grade_id deve ser string, inclusive quando o valor é numérico."""
        p = tmp_path / "vw_grades.csv"
        linha = {**LINHA_AGHU_VALIDA, "Grade": "00042"}
        _escrever_csv(p, [linha])
        provider = GradeAghuCsvProvider(caminho=p)
        grade = provider.listar_grades()[0]
        assert isinstance(grade.grade_id, str)
        assert grade.grade_id == "00042"

    def test_quantidade_vagas_e_inteiro(self, tmp_path):
        """Quantidade_Vagas deve ser armazenada como int."""
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA])
        provider = GradeAghuCsvProvider(caminho=p)
        grade = provider.listar_grades()[0]
        assert isinstance(grade.quantidade_vagas, int)
        assert grade.quantidade_vagas == 12

    def test_quantidade_vagas_nao_e_salas(self, tmp_path):
        """qtd_salas_necessarias NÃO pode ser igual a Quantidade_Vagas."""
        p = tmp_path / "vw_grades.csv"
        linha = {**LINHA_AGHU_VALIDA, "Quantidade_Vagas": "99"}
        _escrever_csv(p, [linha])
        provider = GradeAghuCsvProvider(caminho=p)
        grade = provider.listar_grades()[0]
        assert grade.quantidade_vagas == 99
        assert grade.qtd_salas_necessarias == 1        # regra MVP
        assert grade.qtd_salas_necessarias != grade.quantidade_vagas

    def test_qtd_salas_padrao_e_1(self, tmp_path):
        """No MVP, qtd_salas_necessarias é sempre 1."""
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA])
        provider = GradeAghuCsvProvider(caminho=p)
        grade = provider.listar_grades()[0]
        assert grade.qtd_salas_necessarias == 1

    def test_arquivo_ausente_lanca_file_not_found(self, tmp_path):
        provider = GradeAghuCsvProvider(caminho=tmp_path / "nao_existe.csv")
        with pytest.raises(FileNotFoundError):
            provider.listar_grades()

    def test_csv_vazio_lanca_value_error(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        p.write_text("", encoding="utf-8")
        provider = GradeAghuCsvProvider(caminho=p)
        with pytest.raises(ValueError):
            provider.listar_grades()

    def test_colunas_obrigatorias_ausentes(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        linha_sem_vagas = {k: v for k, v in LINHA_AGHU_VALIDA.items() if k != "Quantidade_Vagas"}
        _escrever_csv(p, [linha_sem_vagas])
        provider = GradeAghuCsvProvider(caminho=p)
        with pytest.raises(ValueError, match="Quantidade_Vagas"):
            provider.listar_grades()

    def test_colunas_extras_nao_quebram(self, tmp_path):
        """O provider deve ignorar colunas extras sem errar."""
        p = tmp_path / "vw_grades.csv"
        linha_com_extra = {**LINHA_AGHU_VALIDA, "Coluna_Extra_Desconhecida": "valor"}
        _escrever_csv(p, [linha_com_extra])
        provider = GradeAghuCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 1

    def test_separador_ponto_e_virgula(self, tmp_path):
        """Provider deve detectar e usar ';' como separador."""
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA], sep=";")
        provider = GradeAghuCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 1
        assert grades[0].especialidade == "CARDIOLOGIA"

    def test_hora_inicio_opcional(self, tmp_path):
        """Hora_Inicio pode estar ausente — deve resultar em None."""
        p = tmp_path / "vw_grades.csv"
        linha_sem_hora = {k: v for k, v in LINHA_AGHU_VALIDA.items() if k != "Hora_Inicio"}
        _escrever_csv(p, [linha_sem_hora])
        provider = GradeAghuCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert grades[0].hora_inicio is None

    def test_buscar_grade_existente(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA])
        provider = GradeAghuCsvProvider(caminho=p)
        grade = provider.buscar_grade("10001")
        assert grade is not None
        assert grade.grade_id == "10001"

    def test_buscar_grade_inexistente_retorna_none(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        _escrever_csv(p, [LINHA_AGHU_VALIDA])
        provider = GradeAghuCsvProvider(caminho=p)
        assert provider.buscar_grade("NAOEXISTE") is None

    def test_multiplas_grades(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        linha2 = {**LINHA_AGHU_VALIDA, "Grade": "20002", "Especialidade": "ORTOPEDIA"}
        _escrever_csv(p, [LINHA_AGHU_VALIDA, linha2])
        provider = GradeAghuCsvProvider(caminho=p)
        grades = provider.listar_grades()
        assert len(grades) == 2

    def test_resumo_importacao(self, tmp_path):
        p = tmp_path / "vw_grades.csv"
        linha_sem_dia = {**LINHA_AGHU_VALIDA, "Grade": "20002", "Dia_da_Semana": ""}
        _escrever_csv(p, [LINHA_AGHU_VALIDA, linha_sem_dia])
        provider = GradeAghuCsvProvider(caminho=p)
        r = provider.resumo_importacao()
        assert r["linhas_lidas"] == 2
        assert "sem dia da semana" in " ".join(r["avisos"]).lower()
