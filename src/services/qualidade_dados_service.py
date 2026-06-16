"""Serviço de qualidade de dados.

Detecta problemas nos CSVs AGHU (grades e consultas) e gera um painel
de qualidade com gravidade categorizada.
"""
from __future__ import annotations

from src.models.schemas import GradeAghu, ProblemaQualidade, QualidadeDados


def _problema(categoria: str, descricao: str, quantidade: int, gravidade: str) -> ProblemaQualidade:
    return ProblemaQualidade(
        categoria=categoria,
        descricao=descricao,
        quantidade=quantidade,
        gravidade=gravidade,
    )


def analisar_qualidade(
    grades: list[GradeAghu],
    linhas_consulta: list[dict],
) -> QualidadeDados:
    problemas: list[ProblemaQualidade] = []

    # ── Problemas em grades ──────────────────────────────────────────────────
    grades_sem_dia = sum(1 for g in grades if not g.dia_semana)
    if grades_sem_dia:
        problemas.append(_problema(
            "Grades", f"{grades_sem_dia} grade(s) sem dia da semana",
            grades_sem_dia, "atencao",
        ))

    grades_sem_hora = sum(1 for g in grades if not g.hora_inicio)
    if grades_sem_hora:
        problemas.append(_problema(
            "Grades", f"{grades_sem_hora} grade(s) sem hora de início",
            grades_sem_hora, "aviso",
        ))

    grades_sem_turno = sum(1 for g in grades if not g.turno)
    if grades_sem_turno:
        problemas.append(_problema(
            "Grades", f"{grades_sem_turno} grade(s) sem turno definido",
            grades_sem_turno, "atencao",
        ))

    # Grades ativas sem horário ativo
    grades_ativas_ids = {
        g.grade_id for g in grades
        if g.situacao_grade.upper() in ("ATIVO", "ATIVA", "HABILITADO", "HABILITADA")
    }
    horarios_ativos_ids = {
        g.grade_id for g in grades
        if g.situacao_horario.upper() in ("ATIVO", "ATIVA", "HABILITADO", "HABILITADA")
    }
    grades_ativas_sem_horario = len(grades_ativas_ids - horarios_ativos_ids)
    if grades_ativas_sem_horario:
        problemas.append(_problema(
            "Grades", f"{grades_ativas_sem_horario} grade(s) ativa(s) sem horário ativo",
            grades_ativas_sem_horario, "atencao",
        ))

    # ── Problemas em consultas ───────────────────────────────────────────────
    if linhas_consulta:
        grades_conhecidas = {g.grade_id for g in grades}

        consultas_sem_grade = sum(1 for linha in linhas_consulta if not linha.get("Grade"))
        if consultas_sem_grade:
            problemas.append(_problema(
                "Consultas", f"{consultas_sem_grade} consulta(s) sem grade associada",
                consultas_sem_grade, "atencao",
            ))

        consultas_grade_inativa = sum(
            1 for linha in linhas_consulta
            if linha.get("Grade") and linha["Grade"] not in grades_conhecidas
        )
        if consultas_grade_inativa:
            problemas.append(_problema(
                "Consultas", f"{consultas_grade_inativa} consulta(s) com grade não encontrada nas grades",
                consultas_grade_inativa, "aviso",
            ))

        consultas_sem_data = sum(
            1 for linha in linhas_consulta
            if not linha.get("Data_Hora_Consulta") and not linha.get("Dt_Hr_Consulta")
        )
        if consultas_sem_data:
            problemas.append(_problema(
                "Consultas", f"{consultas_sem_data} consulta(s) sem data/hora",
                consultas_sem_data, "critico",
            ))

        # Duplicatas por ID (se existir campo identificador)
        ids = [linha.get("Num_Consulta") or linha.get("Num_Consulta_Aghu", "") for linha in linhas_consulta]
        ids_validos = [i for i in ids if i]
        duplicatas = len(ids_validos) - len(set(ids_validos))
        if duplicatas:
            problemas.append(_problema(
                "Consultas", f"{duplicatas} consulta(s) com ID duplicado",
                duplicatas, "atencao",
            ))

    total = len(problemas)
    criticos = sum(1 for p in problemas if p.gravidade == "critico")

    return QualidadeDados(
        problemas=problemas,
        total_problemas=total,
        criticos=criticos,
    )
