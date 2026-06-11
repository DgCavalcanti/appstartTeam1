"""
alocacao_engine.py — Motor de Alocação Automática do SAA

Lógica pura de pontuação e alocação.
Não acessa banco de dados nem arquivos CSV diretamente.
Recebe os dados prontos e devolve o resultado — facilita testes unitários.

Contrato definido em: SPEC.md / 04-modelo-dados.md
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Optional

from src.models.schemas import Grade, Sala, Alocacao, ResultadoAlocacao, ResultadoMotor

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constantes de peso — ajustáveis sem alterar a lógica
# ---------------------------------------------------------------------------

PESO_ESPECIALIDADE_PREFERENCIAL = 40
PESO_ORTOPEDIA_ANDAR_1          = 30
PESO_ORTOPEDIA_ANDAR_2_3        = 10
PESO_ORTOPEDIA_ACESSIVEL        = 20
PESO_MEDICO_MESMO_BLOCO         = 25
PESO_HISTORICO_MESMA_SALA       = 15
PESO_SALA_ACESSIVEL_GERAL       = 5

# Especialidades com restrição física — processadas primeiro
PRIORIDADE_ESPECIALIDADE: dict[str, int] = {
    "oftalmologia": 1,
    "ginecologia":  2,
    "ortopedia":    3,
}
PRIORIDADE_PADRAO = 99

# Status de sala que bloqueiam o uso
STATUS_BLOQUEANTES = {"reforma", "manutencao", "bloqueada"}


# ---------------------------------------------------------------------------
# Regras Bloqueantes — retornam True se a sala DEVE ser eliminada
# ---------------------------------------------------------------------------

def _bloqueada_por_status(sala: Sala) -> bool:
    """B1 — Sala em reforma ou manutenção."""
    return sala.status.lower() in STATUS_BLOQUEANTES


def _bloqueada_para_oftalmologia(grade: Grade, sala: Sala) -> bool:
    """B2 — Oftalmologia exige sala com equipamento específico."""
    if grade.especialidade.lower() == "oftalmologia":
        return not sala.tem_equipamento
    return False


def _bloqueada_para_ginecologia(grade: Grade, sala: Sala) -> bool:
    """B3 — Ginecologia exige maca ginecológica."""
    if grade.especialidade.lower() == "ginecologia":
        return not sala.tem_maca_ginecologica
    return False


def _bloqueada_por_ocupacao(sala: Sala, salas_ocupadas: set[int]) -> bool:
    """B4 — Sala já ocupada no mesmo turno/dia."""
    return sala.id in salas_ocupadas


def sala_e_elegivel(
    grade: Grade,
    sala: Sala,
    salas_ocupadas: set[int],
) -> bool:
    """
    Aplica todas as regras bloqueantes em sequência.
    Retorna True se a sala pode ser candidata para esta grade.
    """
    if _bloqueada_por_status(sala):
        return False
    if _bloqueada_para_oftalmologia(grade, sala):
        return False
    if _bloqueada_para_ginecologia(grade, sala):
        return False
    if _bloqueada_por_ocupacao(sala, salas_ocupadas):
        return False
    return True


# ---------------------------------------------------------------------------
# Regras de Pontuação
# ---------------------------------------------------------------------------

def calcular_score(
    grade: Grade,
    sala: Sala,
    salas_ja_alocadas_ao_medico: list[Sala],
    salas_do_historico_do_medico: set[int],
) -> int:
    """
    Calcula o score de compatibilidade entre uma grade e uma sala candidata.

    Parâmetros:
        grade                         — grade a ser alocada
        sala                          — sala candidata
        salas_ja_alocadas_ao_medico   — salas que o mesmo profissional já recebeu
                                        neste turno (para regra de proximidade)
        salas_do_historico_do_medico  — ids de salas que o profissional usou
                                        em alocações anteriores (histórico)
    """
    score = 0
    especialidade = grade.especialidade.lower()

    # P1 — Especialidade preferencial da sala bate com a grade
    if (
        sala.especialidade_preferencial
        and sala.especialidade_preferencial.lower() == especialidade
    ):
        score += PESO_ESPECIALIDADE_PREFERENCIAL
        logger.debug("P1 +%d (especialidade preferencial)", PESO_ESPECIALIDADE_PREFERENCIAL)

    # P2/P3 — Ortopedia: bonificação por andar
    if especialidade == "ortopedia":
        try:
            andar_num = int(sala.andar)
        except ValueError:
            andar_num = 99  # andares não numéricos recebem penalidade implícita

        if andar_num == 1:
            score += PESO_ORTOPEDIA_ANDAR_1
            logger.debug("P2 +%d (ortopedia andar 1)", PESO_ORTOPEDIA_ANDAR_1)
        elif andar_num in (2, 3):
            score += PESO_ORTOPEDIA_ANDAR_2_3
            logger.debug("P3 +%d (ortopedia andar 2-3)", PESO_ORTOPEDIA_ANDAR_2_3)

        # P4 — Ortopedia: sala acessível
        if sala.acessivel:
            score += PESO_ORTOPEDIA_ACESSIVEL
            logger.debug("P4 +%d (ortopedia acessível)", PESO_ORTOPEDIA_ACESSIVEL)

    # P5 — Médico já tem outra sala alocada no mesmo bloco neste turno
    blocos_do_medico = {s.bloco for s in salas_ja_alocadas_ao_medico}
    if sala.bloco in blocos_do_medico:
        score += PESO_MEDICO_MESMO_BLOCO
        logger.debug("P5 +%d (médico mesmo bloco)", PESO_MEDICO_MESMO_BLOCO)

    # P6 — Médico já usou essa sala em alocações anteriores
    if sala.id in salas_do_historico_do_medico:
        score += PESO_HISTORICO_MESMA_SALA
        logger.debug("P6 +%d (histórico mesma sala)", PESO_HISTORICO_MESMA_SALA)

    # P7 — Sala acessível (bônus genérico)
    if sala.acessivel:
        score += PESO_SALA_ACESSIVEL_GERAL
        logger.debug("P7 +%d (sala acessível geral)", PESO_SALA_ACESSIVEL_GERAL)

    return score


# ---------------------------------------------------------------------------
# Ordenação de Grades por Prioridade
# ---------------------------------------------------------------------------

def _prioridade_grade(grade: Grade) -> int:
    """Retorna o índice de prioridade da grade (menor = processado primeiro)."""
    return PRIORIDADE_ESPECIALIDADE.get(grade.especialidade.lower(), PRIORIDADE_PADRAO)


# ---------------------------------------------------------------------------
# Alocação de Múltiplas Salas (médico em mais de uma sala)
# ---------------------------------------------------------------------------

def _alocar_multiplas_salas(
    grade: Grade,
    candidatas_ordenadas: list[tuple[Sala, int]],
    salas_ocupadas: set[int],
    qtd: int,
) -> tuple[list[Sala], list[int]]:
    """
    Seleciona `qtd` salas para uma grade que exige múltiplas salas.

    Estratégia:
      1. Usa a sala de maior score como âncora (define o bloco preferido).
      2. Para as demais, prioriza salas do mesmo bloco da âncora.
      3. Se não houver salas suficientes no bloco, expande para outros blocos.

    Retorna:
        (salas_escolhidas, scores_correspondentes)
    """
    if not candidatas_ordenadas:
        return [], []

    # Âncora: melhor candidata global
    ancora, score_ancora = candidatas_ordenadas[0]
    bloco_ancora = ancora.bloco

    escolhidas: list[tuple[Sala, int]] = [candidatas_ordenadas[0]]

    # Candidatas restantes ordenadas: mesmo bloco primeiro, depois outros blocos
    restantes = candidatas_ordenadas[1:]
    restantes_mesmo_bloco = [(s, sc) for s, sc in restantes if s.bloco == bloco_ancora]
    restantes_outros       = [(s, sc) for s, sc in restantes if s.bloco != bloco_ancora]
    fila = restantes_mesmo_bloco + restantes_outros

    for sala, sc in fila:
        if len(escolhidas) >= qtd:
            break
        if sala.id not in salas_ocupadas:
            escolhidas.append((sala, sc))

    salas_out  = [s for s, _ in escolhidas]
    scores_out = [sc for _, sc in escolhidas]
    return salas_out, scores_out


# ---------------------------------------------------------------------------
# Motor Principal
# ---------------------------------------------------------------------------

def alocar(
    dia_semana: str,
    turno: str,
    grades: list[Grade],
    salas: list[Sala],
    historico: list[Alocacao],
) -> ResultadoMotor:
    """
    Executa o motor de alocação automática para um dia/turno.

    Parâmetros:
        dia_semana  — ex: "segunda", "terca"
        turno       — "manha" | "tarde"
        grades      — grades do dia/turno a serem alocadas (sem filtro prévio)
        salas       — todas as salas cadastradas
        historico   — alocações anteriores (para preferência de profissional)

    Retorna:
        ResultadoMotor com alocações geradas e grades sem alocação
    """
    logger.info("Motor iniciado: %s %s | %d grades | %d salas", dia_semana, turno, len(grades), len(salas))

    # Filtra grades do dia/turno solicitado
    grades_do_turno = [
        g for g in grades
        if g.dia_semana.lower() == dia_semana.lower()
        and g.turno.lower() == turno.lower()
    ]

    # Ordena por prioridade de restrição física
    grades_ordenadas = sorted(grades_do_turno, key=_prioridade_grade)

    # Pré-computa histórico: profissional -> set de ids de salas já usadas
    historico_por_profissional: dict[str, set[int]] = {}
    for aloc in historico:
        grade_ref = next((g for g in grades if g.id == aloc.id_grade), None)
        if grade_ref:
            historico_por_profissional.setdefault(grade_ref.profissional, set()).add(aloc.id_sala)

    salas_ocupadas: set[int] = set()
    # Rastreia salas alocadas por profissional neste turno (para regra P5)
    salas_alocadas_por_profissional: dict[str, list[Sala]] = {}

    alocacoes: list[ResultadoAlocacao] = []
    grades_sem_alocacao: list[int] = []

    for grade in grades_ordenadas:
        logger.debug("Processando grade id=%d esp=%s prof=%s qtd=%d",
                     grade.id, grade.especialidade, grade.profissional, grade.qtd_salas_necessarias)

        # Filtra salas elegíveis (regras bloqueantes)
        candidatas = [s for s in salas if sala_e_elegivel(grade, s, salas_ocupadas)]

        if not candidatas:
            logger.warning("Grade id=%d sem salas candidatas após filtro bloqueante", grade.id)
            grades_sem_alocacao.append(grade.id)
            alocacoes.append(ResultadoAlocacao(
                id_grade=grade.id,
                especialidade=grade.especialidade,
                profissional=grade.profissional,
                salas_alocadas=[],
                scores=[],
                alocado=False,
            ))
            continue

        # Recupera contexto do profissional
        salas_do_medico_no_turno   = salas_alocadas_por_profissional.get(grade.profissional, [])
        salas_do_medico_historico  = historico_por_profissional.get(grade.profissional, set())

        # Calcula score para cada candidata e ordena (maior score primeiro)
        candidatas_com_score: list[tuple[Sala, int]] = sorted(
            [
                (sala, calcular_score(grade, sala, salas_do_medico_no_turno, salas_do_medico_historico))
                for sala in candidatas
            ],
            key=lambda x: x[1],
            reverse=True,
        )

        qtd = grade.qtd_salas_necessarias

        if qtd == 1:
            sala_escolhida, score = candidatas_com_score[0]
            salas_escolhidas = [sala_escolhida]
            scores_escolhidos = [score]
        else:
            salas_escolhidas, scores_escolhidos = _alocar_multiplas_salas(
                grade, candidatas_com_score, salas_ocupadas, qtd
            )

        # Verifica se conseguiu o número necessário de salas
        if len(salas_escolhidas) < qtd:
            logger.warning(
                "Grade id=%d precisava de %d salas, conseguiu apenas %d",
                grade.id, qtd, len(salas_escolhidas)
            )
            # Aloca o que foi possível e registra como parcialmente alocado
            grades_sem_alocacao.append(grade.id)

        # Persiste escolhas no estado do turno
        for sala in salas_escolhidas:
            salas_ocupadas.add(sala.id)
            salas_alocadas_por_profissional.setdefault(grade.profissional, []).append(sala)

        alocacoes.append(ResultadoAlocacao(
            id_grade=grade.id,
            especialidade=grade.especialidade,
            profissional=grade.profissional,
            salas_alocadas=[s.id for s in salas_escolhidas],
            scores=scores_escolhidos,
            alocado=len(salas_escolhidas) == qtd,
        ))

        logger.info(
            "Grade id=%d → salas %s (scores %s)",
            grade.id,
            [s.id for s in salas_escolhidas],
            scores_escolhidos,
        )

    logger.info(
        "Motor finalizado: %d alocadas | %d sem alocação",
        sum(1 for a in alocacoes if a.alocado),
        len(grades_sem_alocacao),
    )

    return ResultadoMotor(
        dia_semana=dia_semana,
        turno=turno,
        alocacoes=alocacoes,
        grades_sem_alocacao=grades_sem_alocacao,
    )
