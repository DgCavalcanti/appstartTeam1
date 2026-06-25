from __future__ import annotations

from src.models.schemas import Alocacao, Grade, Sala
from src.services.alocacao_engine import alocar, calcular_score, sala_e_elegivel


def _grade(**kw) -> Grade:
    defaults = dict(
        id="G001",
        especialidade="Cardiologia",
        profissional="Dr. A",
        dia_semana="Segunda",
        turno="Manhã",
        qtd_salas_necessarias=1,
    )
    return Grade(**{**defaults, **kw})


def _sala(**kw) -> Sala:
    defaults = dict(
        id="S001",
        numero="101",
        bloco="A",
        andar="1",
        status="disponivel",
        acessibilidade=True,
        equipamentos=[],
        especialidade_preferencial=None,
    )
    return Sala(**{**defaults, **kw})


def test_alocar_normaliza_turno_sem_acento():
    resultado = alocar(
        dia_semana="segunda",
        turno="manha",
        grades=[_grade()],
        salas=[_sala()],
        historico=[],
    )

    assert len(resultado.alocacoes) == 1
    assert resultado.alocacoes[0].alocado is True
    assert resultado.alocacoes[0].salas_alocadas == ["S001"]


def test_ortopedia_aghu_com_sufixo_recebe_bonus_de_score():
    grade = _grade(especialidade="ORTOPEDIA (AMBULATÓRIO)")
    sala = _sala(andar="1", acessibilidade=True)

    score = calcular_score(
        grade=grade,
        sala=sala,
        salas_ja_alocadas_ao_medico=[],
        salas_do_historico_do_medico=set(),
    )

    assert score >= 55


def test_ginecologia_aghu_com_sufixo_exige_equipamento_normalizado():
    grade = _grade(especialidade="GINECOLOGIA (AMBULATÓRIO)")
    sala_sem_maca = _sala(equipamentos=[])
    sala_com_maca = _sala(equipamentos=["Maca_Ginecologica"])

    assert sala_e_elegivel(grade, sala_sem_maca, salas_ocupadas=set()) is False
    assert sala_e_elegivel(grade, sala_com_maca, salas_ocupadas=set()) is True


def test_historico_com_turno_acentuado_nao_impede_alocacao_nova():
    resultado = alocar(
        dia_semana="segunda",
        turno="manha",
        grades=[_grade()],
        salas=[_sala()],
        historico=[
            Alocacao(
                id="A001",
                grade_id="G999",
                sala_id="S999",
                dia_semana="Segunda",
                turno="Manhã",
            )
        ],
    )

    assert resultado.alocacoes[0].alocado is True
