"""
test_importacao.py — Testes do pipeline de importação e tratamento (etapa 1).

Cobre os 10 passos da seção 6 do SAA_Arquitetura.pdf, um a um, e fecha com a
integração ponta a ponta: planilha do AGHU → demanda → motor de alocação.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.domain.alocacao import EntradaAlocacao, SolverHeuristico
from src.domain.entidades import NUM_TURNOS, Pavimento, indice_turno
from src.domain.importacao import (
    Catalogo,
    GradeDemanda,
    GradeSlot,
    executar_pipeline,
    importar,
    ler_planilha,
    normalizar,
    para_clinicas,
)
from src.domain.importacao.leitor import ErroDeLeitura, descartar_colunas_irrelevantes
from src.domain.importacao.regras import (
    canonizar_dia,
    canonizar_periodo,
    derivar_demanda,
    deduplicar_em_slots,
    filtrar_condicao_de_atendimento,
    filtrar_dias,
    filtrar_situacao,
    filtrar_turno_noite,
    filtrar_unidades,
)

#: Amostra real exportada do AGHU, versionada fora do git.
AMOSTRA_REAL = Path("data/importados/vw_grades.20260625114053.csv")


# ---------------------------------------------------------------------------
# Auxiliares
# ---------------------------------------------------------------------------


def linha(
    profissional: str = "Dr. A",
    unidade: str = "CARDIOLOGIA (AMBULATÓRIO)",
    condicao: str = "RETORNO",
    situacao_grade: str = "Ativo",
    situacao_horario: str = "Ativo",
    dia: str = "Segunda",
    turno: str = "Manhã",
    **extras,
) -> dict:
    base = {
        "Profissional_Grade": profissional,
        "Unidade_Funcional": unidade,
        "Condicao_De_Atendimento": condicao,
        "Situacao_Atual_Grade": situacao_grade,
        "Situacao_Atual_Horario": situacao_horario,
        "Dia_da_Semana": dia,
        "Turno": turno,
    }
    base.update(extras)
    return base


def frame(*linhas: dict) -> pd.DataFrame:
    return pd.DataFrame(list(linhas))


# ---------------------------------------------------------------------------
# Normalização
# ---------------------------------------------------------------------------


class TestNormalizacao:

    def test_remove_acento_e_baixa_caixa(self):
        assert normalizar("Terça") == "terca"
        assert normalizar("MANHÃ") == "manha"
        assert normalizar("Sessão") == "sessao"

    def test_colapsa_espacos(self):
        assert normalizar("  PRIMEIRA   CONSULTA  ") == "primeira consulta"

    def test_valores_vazios(self):
        assert normalizar(None) == ""
        assert normalizar(float("nan")) == ""

    def test_canonizar_dia(self):
        assert canonizar_dia("Segunda") == "segunda"
        assert canonizar_dia("Terça") == "terca"
        assert canonizar_dia("SEXTA-FEIRA") == "sexta"

    def test_canonizar_dia_rejeita_fim_de_semana(self):
        assert canonizar_dia("Sábado") is None
        assert canonizar_dia("Domingo") is None
        assert canonizar_dia("qualquer coisa") is None

    def test_canonizar_periodo(self):
        assert canonizar_periodo("Manhã") == "manha"
        assert canonizar_periodo("TARDE") == "tarde"

    def test_canonizar_periodo_rejeita_noite(self):
        assert canonizar_periodo("Noite") is None


# ---------------------------------------------------------------------------
# Passo 1 — leitura
# ---------------------------------------------------------------------------


class TestLeitura:

    def test_arquivo_inexistente(self):
        with pytest.raises(ErroDeLeitura, match="não encontrado"):
            ler_planilha("data/nao_existe.csv")

    def test_extensao_nao_suportada(self, tmp_path):
        arquivo = tmp_path / "grades.txt"
        arquivo.write_text("qualquer coisa", encoding="utf-8")
        with pytest.raises(ErroDeLeitura, match="extensão não suportada"):
            ler_planilha(arquivo)

    def test_colunas_ausentes(self, tmp_path):
        arquivo = tmp_path / "grades.csv"
        arquivo.write_text("Coluna_A,Coluna_B\n1,2\n", encoding="utf-8")
        with pytest.raises(ErroDeLeitura, match="colunas ausentes"):
            ler_planilha(arquivo)

    def test_le_csv_latin1(self, tmp_path):
        arquivo = tmp_path / "grades.csv"
        conteudo = (
            "Profissional_Grade,Unidade_Funcional,Condicao_De_Atendimento,"
            "Situacao_Atual_Grade,Situacao_Atual_Horario,Dia_da_Semana,Turno\n"
            "Dr. José,CARDIOLOGIA,RETORNO,Ativo,Ativo,Terça,Manhã\n"
        )
        arquivo.write_bytes(conteudo.encode("latin-1"))
        df = ler_planilha(arquivo)
        assert len(df) == 1
        assert df.iloc[0]["Profissional_Grade"] == "Dr. José"

    def test_le_csv_utf8_com_bom(self, tmp_path):
        arquivo = tmp_path / "grades.csv"
        conteudo = (
            "Profissional_Grade,Unidade_Funcional,Condicao_De_Atendimento,"
            "Situacao_Atual_Grade,Situacao_Atual_Horario,Dia_da_Semana,Turno\n"
            "Dra. Ana,GINECOLOGIA,RETORNO,Ativo,Ativo,Sexta,Tarde\n"
        )
        arquivo.write_bytes(b"\xef\xbb\xbf" + conteudo.encode("utf-8"))
        df = ler_planilha(arquivo)
        assert list(df.columns)[0] == "Profissional_Grade", "o BOM não foi removido"


# ---------------------------------------------------------------------------
# Passo 6 — colunas irrelevantes
# ---------------------------------------------------------------------------


class TestDescarteDeColunas:

    def test_remove_hora_vagas_e_especialidade(self):
        df = frame(
            linha(
                Hora_Inicio="1970-01-01 07:00:00.000",
                Quantidade_Vagas="20",
                Especialidade="CARDIOLOGIA",
                Grade="12",
            )
        )
        resultado = descartar_colunas_irrelevantes(df)
        for coluna in ("Hora_Inicio", "Quantidade_Vagas", "Especialidade", "Grade"):
            assert coluna not in resultado.columns
        assert "Unidade_Funcional" in resultado.columns

    def test_nao_falha_quando_a_coluna_nao_existe(self):
        df = frame(linha())
        assert len(descartar_colunas_irrelevantes(df).columns) == 7


# ---------------------------------------------------------------------------
# Passos 2 a 5 e 7 — filtros
# ---------------------------------------------------------------------------


class TestFiltros:

    def test_passo_2_unidade_que_nao_participa(self):
        df = frame(
            linha(unidade="CARDIOLOGIA (AMBULATÓRIO)"),
            linha(unidade="ALMOXARIFADO"),
        )
        resultado = filtrar_unidades(df, frozenset({"almoxarifado"}))
        assert len(resultado) == 1
        assert resultado.iloc[0]["Unidade_Funcional"] == "CARDIOLOGIA (AMBULATÓRIO)"

    def test_passo_3_condicoes_que_nao_ocupam_sala(self):
        df = frame(
            linha(condicao="RETORNO"),
            linha(condicao="Registro em Prontuário"),
            linha(condicao="Sessão"),
            linha(condicao="Teleatendimento"),
            linha(condicao="PRIMEIRA CONSULTA"),
        )
        resultado = filtrar_condicao_de_atendimento(df)
        assert len(resultado) == 2
        restantes = set(resultado["Condicao_De_Atendimento"])
        assert restantes == {"RETORNO", "PRIMEIRA CONSULTA"}

    def test_passo_4_exige_grade_e_horario_ativos(self):
        df = frame(
            linha(situacao_grade="Ativo", situacao_horario="Ativo"),
            linha(situacao_grade="Ativo", situacao_horario="Inativo"),
            linha(situacao_grade="Inativo", situacao_horario="Ativo"),
            linha(situacao_grade="Inativo", situacao_horario="Inativo"),
        )
        assert len(filtrar_situacao(df)) == 1

    def test_passo_5_sabado_sai(self):
        df = frame(
            linha(dia="Segunda"),
            linha(dia="Sábado"),
            linha(dia="Sexta"),
        )
        resultado = filtrar_dias(df)
        assert len(resultado) == 2
        assert "Sábado" not in set(resultado["Dia_da_Semana"])

    def test_passo_7_noite_sai(self):
        df = frame(
            linha(turno="Manhã"),
            linha(turno="Tarde"),
            linha(turno="Noite"),
        )
        resultado = filtrar_turno_noite(df)
        assert len(resultado) == 2
        assert "Noite" not in set(resultado["Turno"])


# ---------------------------------------------------------------------------
# Passo 8 — deduplicação
# ---------------------------------------------------------------------------


class TestDeduplicacao:

    def test_varias_condicoes_viram_um_slot(self):
        # O mesmo médico, na mesma clínica e turno, ocupa uma sala só —
        # independentemente de quantas condições de atendimento ele registre.
        df = frame(
            linha(profissional="Dr. A", condicao="RETORNO"),
            linha(profissional="Dr. A", condicao="PRIMEIRA CONSULTA"),
            linha(profissional="Dr. A", condicao="INTERCONSULTA"),
        )
        slots = deduplicar_em_slots(df)
        assert len(slots) == 1
        assert slots[0].profissional == "Dr. A"
        assert slots[0].revisar is False

    def test_turnos_distintos_geram_slots_distintos(self):
        df = frame(
            linha(profissional="Dr. A", dia="Segunda", turno="Manhã"),
            linha(profissional="Dr. A", dia="Segunda", turno="Tarde"),
            linha(profissional="Dr. A", dia="Terça", turno="Manhã"),
        )
        assert len(deduplicar_em_slots(df)) == 3

    def test_profissional_em_duas_clinicas_conta_em_cada_uma(self):
        # Os ~7% de casos do arquivo real: o slot conta nas duas clínicas,
        # porque ambas de fato reservam espaço, e fica marcado para revisão.
        df = frame(
            linha(profissional="Dr. A", unidade="CARDIOLOGIA", dia="Segunda", turno="Manhã"),
            linha(profissional="Dr. A", unidade="CLÍNICA MÉDICA", dia="Segunda", turno="Manhã"),
        )
        slots = deduplicar_em_slots(df)

        assert len(slots) == 2
        assert {s.unidade for s in slots} == {"CARDIOLOGIA", "CLÍNICA MÉDICA"}
        assert all(s.revisar for s in slots), "ambos deveriam ir para revisão"

    def test_mesma_clinica_em_turnos_diferentes_nao_vai_para_revisao(self):
        df = frame(
            linha(profissional="Dr. A", unidade="CARDIOLOGIA", turno="Manhã"),
            linha(profissional="Dr. A", unidade="CLÍNICA MÉDICA", turno="Tarde"),
        )
        slots = deduplicar_em_slots(df)
        assert len(slots) == 2
        assert not any(s.revisar for s in slots)

    def test_dataframe_vazio(self):
        assert deduplicar_em_slots(frame()) == ()

    def test_ordem_e_estavel(self):
        df = frame(
            linha(profissional="Dr. Z", unidade="ZZZ"),
            linha(profissional="Dr. A", unidade="AAA"),
        )
        assert deduplicar_em_slots(df) == deduplicar_em_slots(df)


# ---------------------------------------------------------------------------
# Passo 9 — derivação da demanda
# ---------------------------------------------------------------------------


class TestDerivarDemanda:

    def test_conta_slots_por_unidade_dia_turno(self):
        slots = (
            GradeSlot("Dr. A", "CARDIO", "segunda", "manha"),
            GradeSlot("Dr. B", "CARDIO", "segunda", "manha"),
            GradeSlot("Dr. C", "CARDIO", "segunda", "tarde"),
            GradeSlot("Dr. D", "ORTO", "segunda", "manha"),
        )
        demandas = derivar_demanda(slots)
        por_chave = {(d.unidade, d.dia, d.periodo): d.quantidade for d in demandas}

        assert por_chave[("CARDIO", "segunda", "manha")] == 2
        assert por_chave[("CARDIO", "segunda", "tarde")] == 1
        assert por_chave[("ORTO", "segunda", "manha")] == 1

    def test_sem_slots(self):
        assert derivar_demanda(()) == ()

    def test_a_soma_das_quantidades_e_o_total_de_slots(self):
        slots = tuple(
            GradeSlot(f"Dr. {i}", "CARDIO", "segunda", "manha") for i in range(7)
        )
        assert sum(d.quantidade for d in derivar_demanda(slots)) == 7


# ---------------------------------------------------------------------------
# Passo 10 — reconciliação com o catálogo
# ---------------------------------------------------------------------------


class TestReconciliacao:

    def test_unidade_nunca_vista_e_apontada(self):
        df = frame(
            linha(unidade="CARDIOLOGIA (AMBULATÓRIO)"),
            linha(unidade="CLÍNICA NOVA"),
        )
        catalogo = Catalogo(unidades_conhecidas=frozenset({"cardiologia (ambulatorio)"}))
        resultado = executar_pipeline(df, catalogo)

        assert resultado.unidades_novas == ("CLÍNICA NOVA",)
        assert resultado.precisa_de_reconciliacao is True

    def test_condicao_nunca_vista_e_apontada(self):
        df = frame(linha(condicao="MUTIRÃO"))
        catalogo = Catalogo(condicoes_conhecidas=frozenset({"retorno"}))
        resultado = executar_pipeline(df, catalogo)

        assert resultado.condicoes_novas == ("MUTIRÃO",)

    def test_catalogo_completo_nao_gera_novidade(self):
        df = frame(linha(unidade="CARDIO", condicao="RETORNO"))
        catalogo = Catalogo(
            unidades_conhecidas=frozenset({"cardio"}),
            condicoes_conhecidas=frozenset({"retorno"}),
        )
        resultado = executar_pipeline(df, catalogo)

        assert resultado.unidades_novas == ()
        assert resultado.condicoes_novas == ()
        assert resultado.precisa_de_reconciliacao is False

    def test_catalogo_normaliza_a_grafia_recebida(self):
        # Sem isso, um acento fora do lugar faria o filtro do passo 2 virar um
        # no-op silencioso — e unidades que não participam entrariam na conta.
        catalogo = Catalogo(
            unidades_excluidas={"FARMÁCIA CENTRAL"},
            unidades_conhecidas={"Cardiologia"},
            condicoes_conhecidas={"RETORNO"},
        )
        assert catalogo.unidades_excluidas == frozenset({"farmacia central"})
        assert catalogo.unidades_conhecidas == frozenset({"cardiologia"})
        assert catalogo.condicoes_conhecidas == frozenset({"retorno"})

    def test_unidade_excluida_casa_apesar_do_acento(self):
        df = frame(
            linha(unidade="FARMACIA CENTRAL"),
            linha(profissional="Dr. B", unidade="CARDIOLOGIA"),
        )
        catalogo = Catalogo(unidades_excluidas={"Farmácia Central"})
        resultado = executar_pipeline(df, catalogo)

        assert resultado.relatorio.descartadas_por_unidade == 1
        assert [s.unidade for s in resultado.slots] == ["CARDIOLOGIA"]

    def test_novidade_e_detectada_mesmo_em_unidade_excluida(self):
        # O gestor precisa saber que a unidade existe, mesmo que ela não entre.
        df = frame(linha(unidade="ALMOXARIFADO"))
        catalogo = Catalogo(unidades_excluidas=frozenset({"almoxarifado"}))
        resultado = executar_pipeline(df, catalogo)

        assert resultado.unidades_novas == ("ALMOXARIFADO",)
        assert resultado.slots == (), "a unidade excluída não pode gerar demanda"


# ---------------------------------------------------------------------------
# Pipeline completo e relatório
# ---------------------------------------------------------------------------


class TestPipelineCompleto:

    @staticmethod
    def _planilha_com_de_tudo() -> pd.DataFrame:
        return frame(
            # Duas linhas que sobrevivem e colapsam num slot só.
            linha(profissional="Dr. A", condicao="RETORNO"),
            linha(profissional="Dr. A", condicao="PRIMEIRA CONSULTA"),
            # Um slot em outro turno.
            linha(profissional="Dr. B", turno="Tarde"),
            # Descartados, um por motivo.
            linha(profissional="Dr. C", situacao_grade="Inativo"),
            linha(profissional="Dr. D", condicao="Teleatendimento"),
            linha(profissional="Dr. E", unidade="ALMOXARIFADO"),
            linha(profissional="Dr. F", dia="Sábado"),
            linha(profissional="Dr. G", turno="Noite"),
        )

    def test_contagens_do_relatorio(self):
        catalogo = Catalogo(unidades_excluidas=frozenset({"almoxarifado"}))
        resultado = executar_pipeline(self._planilha_com_de_tudo(), catalogo)
        r = resultado.relatorio

        assert r.linhas_brutas == 8
        assert r.descartadas_por_situacao == 1
        assert r.descartadas_por_condicao == 1
        assert r.descartadas_por_unidade == 1
        assert r.descartadas_por_dia == 1
        assert r.descartadas_por_noite == 1
        assert r.linhas_apos_filtros == 3
        assert r.total_slots == 2, "as duas condições do Dr. A viram um slot"

    def test_o_descarte_da_noite_e_registrado(self):
        # O documento pede explicitamente que o gestor veja quantos slots saíram.
        df = frame(
            linha(turno="Manhã"),
            linha(profissional="Dr. B", turno="Noite"),
            linha(profissional="Dr. C", turno="Noite"),
        )
        resultado = executar_pipeline(df)
        assert resultado.relatorio.descartadas_por_noite == 2

    def test_resumo_tem_uma_linha_por_etapa(self):
        resultado = executar_pipeline(self._planilha_com_de_tudo())
        assert len(resultado.relatorio.resumo().splitlines()) == 4

    def test_relatorio_de_planilha_vazia_nao_divide_por_zero(self):
        vazia = pd.DataFrame(
            columns=[
                "Profissional_Grade",
                "Unidade_Funcional",
                "Condicao_De_Atendimento",
                "Situacao_Atual_Grade",
                "Situacao_Atual_Horario",
                "Dia_da_Semana",
                "Turno",
            ]
        )
        r = executar_pipeline(vazia).relatorio
        assert r.linhas_brutas == 0
        assert r.percentual_slots == 0.0

    def test_a_reducao_segue_a_ordem_do_documento(self):
        resultado = executar_pipeline(self._planilha_com_de_tudo())
        r = resultado.relatorio
        assert r.linhas_brutas >= r.linhas_apos_filtros >= r.total_slots >= r.total_demandas


# ---------------------------------------------------------------------------
# Ponte para o motor
# ---------------------------------------------------------------------------


class TestParaClinicas:

    def test_monta_vetor_de_dez_turnos(self):
        demandas = (
            GradeDemanda("CARDIO", "segunda", "manha", 3),
            GradeDemanda("CARDIO", "sexta", "tarde", 2),
        )
        (clinica,) = para_clinicas(demandas)

        assert len(clinica.demanda) == NUM_TURNOS
        assert clinica.demanda[indice_turno("segunda", "manha")] == 3
        assert clinica.demanda[indice_turno("sexta", "tarde")] == 2
        assert clinica.total == 5
        assert clinica.pico == 3

    def test_ids_sao_estaveis_e_alfabeticos(self):
        demandas = (
            GradeDemanda("ZZZ", "segunda", "manha", 1),
            GradeDemanda("AAA", "segunda", "manha", 1),
        )
        clinicas = para_clinicas(demandas)

        assert [c.nome for c in clinicas] == ["AAA", "ZZZ"]
        assert [c.id for c in clinicas] == [1, 2]
        assert para_clinicas(demandas) == clinicas

    def test_sem_demanda(self):
        assert para_clinicas(()) == ()


# ---------------------------------------------------------------------------
# Integração: arquivo real do AGHU
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not AMOSTRA_REAL.exists(), reason="amostra do AGHU não disponível neste ambiente"
)
class TestAmostraReal:

    def test_importa_a_amostra_do_aghu(self):
        resultado = importar(AMOSTRA_REAL)
        r = resultado.relatorio

        assert r.linhas_brutas == 10
        # Uma linha vem com Situação Inativo na amostra.
        assert r.descartadas_por_situacao == 1
        assert r.linhas_apos_filtros == 9
        assert r.total_slots == 9

    def test_toda_unidade_da_amostra_e_novidade_num_catalogo_vazio(self):
        resultado = importar(AMOSTRA_REAL)
        assert len(resultado.unidades_novas) == 10
        assert resultado.precisa_de_reconciliacao is True

    def test_a_demanda_da_amostra_alimenta_o_motor(self):
        resultado = importar(AMOSTRA_REAL)
        clinicas = para_clinicas(resultado.demandas)

        assert len(clinicas) == 9, "9 unidades sobrevivem aos filtros"
        assert sum(c.total for c in clinicas) == resultado.relatorio.total_slots


# ---------------------------------------------------------------------------
# Integração ponta a ponta: planilha → demanda → alocação
# ---------------------------------------------------------------------------


class TestPontaAPonta:

    def test_da_planilha_ate_a_alocacao(self):
        # Três clínicas com perfis distintos, escritas como o AGHU exportaria.
        linhas = []
        for i in range(6):
            linhas.append(
                linha(profissional=f"Dr. Manhã {i}", unidade="CARDIOLOGIA", dia="Segunda", turno="Manhã")
            )
        for i in range(5):
            linhas.append(
                linha(profissional=f"Dr. Tarde {i}", unidade="ORTOPEDIA", dia="Segunda", turno="Tarde")
            )
        for i in range(3):
            linhas.append(
                linha(profissional=f"Dr. Sexta {i}", unidade="PEDIATRIA", dia="Sexta", turno="Manhã")
            )
        # Ruído que precisa desaparecer no caminho.
        linhas.append(linha(profissional="Dr. Noite", unidade="CARDIOLOGIA", turno="Noite"))
        linhas.append(linha(profissional="Dr. Sábado", unidade="CARDIOLOGIA", dia="Sábado"))

        resultado = executar_pipeline(frame(*linhas))
        clinicas = para_clinicas(resultado.demandas)

        assert {c.nome for c in clinicas} == {"CARDIOLOGIA", "ORTOPEDIA", "PEDIATRIA"}

        por_nome = {c.nome: c for c in clinicas}
        assert por_nome["CARDIOLOGIA"].demanda[indice_turno("segunda", "manha")] == 6
        assert por_nome["ORTOPEDIA"].demanda[indice_turno("segunda", "tarde")] == 5
        assert por_nome["PEDIATRIA"].demanda[indice_turno("sexta", "manha")] == 3

        # E o motor consome isso sem nenhuma adaptação.
        pavimentos = (
            Pavimento(id=1, nome="Térreo", capacidade=8),
            Pavimento(id=2, nome="1º andar", capacidade=8),
        )
        alocacao = SolverHeuristico().resolver(
            EntradaAlocacao(clinicas=clinicas, pavimentos=pavimentos)
        )

        assert alocacao.total_nao_alocado == 0
        assert alocacao.total_alocado == sum(c.total for c in clinicas)
        assert len(alocacao.por_clinica) == 3

    def test_a_demanda_total_bate_com_os_slots(self):
        # Invariante do passo 9: a demanda é uma projeção fiel dos slots.
        linhas = [
            linha(profissional=f"Dr. {i}", unidade=f"CLÍNICA {i % 4}", dia="Terça")
            for i in range(20)
        ]
        resultado = executar_pipeline(frame(*linhas))
        clinicas = para_clinicas(resultado.demandas)

        assert sum(c.total for c in clinicas) == resultado.relatorio.total_slots
        assert sum(d.quantidade for d in resultado.demandas) == len(resultado.slots)
