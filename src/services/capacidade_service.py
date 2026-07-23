"""Serviço de capacidade ambulatorial.

Calcula indicadores consolidados a partir dos dados de grades e consultas AGHU.
Toda lógica aqui é stateless — recebe listas e devolve resultados.
"""
from __future__ import annotations

from src.models.schemas import (
    CapacidadeResumo,
    GradeAghu,
    ResumoEspecialidade,
    ResumoDiaTurno,
)
from src.repositories.implementations.consulta_aghu_csv_provider import (
    SITUACOES_BLOQUEIO,
    SITUACOES_LIVRE,
    SITUACOES_MARCADA,
    _parse_bool_flag,
    _situacao_normalizada,
)


def _classificar_situacao(situacao: str) -> str:
    """Retorna 'marcada' | 'livre' | 'bloqueio' | 'outra'."""
    s = _situacao_normalizada(situacao)
    if s in SITUACOES_MARCADA:
        return "marcada"
    if s in SITUACOES_LIVRE:
        return "livre"
    if s in SITUACOES_BLOQUEIO:
        return "bloqueio"
    return "outra"


def calcular_resumo(
    grades: list[GradeAghu],
    linhas_consulta: list[dict],
) -> CapacidadeResumo:
    total_grades = len(grades)
    total_grades_ativas = sum(
        1 for g in grades if g.situacao_grade.upper() in ("ATIVO", "ATIVA", "HABILITADO", "HABILITADA")
    )
    total_horarios_ativos = sum(
        1 for g in grades if g.situacao_horario.upper() in ("ATIVO", "ATIVA", "HABILITADO", "HABILITADA")
    )

    total = len(linhas_consulta)
    marcadas = 0
    livres = 0
    bloqueios = 0
    excedentes = 0

    for linha in linhas_consulta:
        classe = _classificar_situacao(linha.get("Situacao_Consulta", ""))
        if classe == "marcada":
            marcadas += 1
        elif classe == "livre":
            livres += 1
        elif classe == "bloqueio":
            bloqueios += 1
        if _parse_bool_flag(linha.get("Consulta_Excedente", "")) is True:
            excedentes += 1

    denom_ocupacao = marcadas + livres
    taxa_ocupacao = round(marcadas / denom_ocupacao, 4) if denom_ocupacao else 0.0
    taxa_excedente = round(excedentes / total, 4) if total else 0.0

    return CapacidadeResumo(
        total_grades=total_grades,
        total_grades_ativas=total_grades_ativas,
        total_horarios_ativos=total_horarios_ativos,
        total_consultas=total,
        consultas_marcadas=marcadas,
        vagas_livres=livres,
        bloqueios=bloqueios,
        consultas_excedentes=excedentes,
        taxa_ocupacao=taxa_ocupacao,
        taxa_excedente=taxa_excedente,
    )


def resumo_por_especialidade(linhas_consulta: list[dict]) -> list[ResumoEspecialidade]:
    agrupado: dict[str, dict] = {}

    for linha in linhas_consulta:
        esp = linha.get("Especialidade", "").strip() or "SEM ESPECIALIDADE"
        if esp not in agrupado:
            agrupado[esp] = {"total": 0, "marcadas": 0, "livres": 0, "bloqueios": 0, "excedentes": 0}
        agrupado[esp]["total"] += 1

        classe = _classificar_situacao(linha.get("Situacao_Consulta", ""))
        if classe == "marcada":
            agrupado[esp]["marcadas"] += 1
        elif classe == "livre":
            agrupado[esp]["livres"] += 1
        elif classe == "bloqueio":
            agrupado[esp]["bloqueios"] += 1

        if _parse_bool_flag(linha.get("Consulta_Excedente", "")) is True:
            agrupado[esp]["excedentes"] += 1

    resultado: list[ResumoEspecialidade] = []
    for esp, d in sorted(agrupado.items()):
        denom = d["marcadas"] + d["livres"]
        taxa_occ = round(d["marcadas"] / denom, 4) if denom else 0.0
        taxa_exc = round(d["excedentes"] / d["total"], 4) if d["total"] else 0.0
        resultado.append(ResumoEspecialidade(
            especialidade=esp,
            total_consultas=d["total"],
            marcadas=d["marcadas"],
            livres=d["livres"],
            bloqueios=d["bloqueios"],
            excedentes=d["excedentes"],
            taxa_ocupacao=taxa_occ,
            taxa_excedente=taxa_exc,
        ))

    return resultado


def resumo_por_dia_turno(linhas_consulta: list[dict]) -> list[ResumoDiaTurno]:
    agrupado: dict[tuple[str, str], dict] = {}

    for linha in linhas_consulta:
        dia = linha.get("Dia_da_Semana", "").strip() or "SEM DIA"
        turno = linha.get("Turno", "").strip() or "SEM TURNO"
        chave = (dia, turno)
        if chave not in agrupado:
            agrupado[chave] = {"marcadas": 0, "livres": 0, "bloqueios": 0, "excedentes": 0}

        classe = _classificar_situacao(linha.get("Situacao_Consulta", ""))
        if classe == "marcada":
            agrupado[chave]["marcadas"] += 1
        elif classe == "livre":
            agrupado[chave]["livres"] += 1
        elif classe == "bloqueio":
            agrupado[chave]["bloqueios"] += 1

        if _parse_bool_flag(linha.get("Consulta_Excedente", "")) is True:
            agrupado[chave]["excedentes"] += 1

    return [
        ResumoDiaTurno(
            dia_semana=dia,
            turno=turno,
            consultas_marcadas=d["marcadas"],
            vagas_livres=d["livres"],
            bloqueios=d["bloqueios"],
            excedentes=d["excedentes"],
        )
        for (dia, turno), d in sorted(agrupado.items())
    ]
