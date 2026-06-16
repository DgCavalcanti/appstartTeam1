"""
conflito_service.py — Motor de verificação de conflitos do SAA.

Recebe grades, salas, restrições e alocações; retorna lista de Conflito.
Não altera estado — função pura sem efeitos colaterais.

Regras implementadas (MVP):
  C01 — Sala em reforma sendo utilizada               → critico
  C02 — Sala em manutenção sendo utilizada            → critico
  C03 — Sala bloqueada sendo utilizada                → critico
  C04 — Sala inexistente em uma alocação              → critico
  C05 — Grade inexistente em uma alocação             → critico
  C06 — Dupla alocação (mesma sala, dia e turno)      → critico
  C07 — Grade sem sala associada                      → critico
  C08 — Especialidade em sala incompatível            → operacional
  C09 — Equipamento obrigatório ausente               → operacional
  C10 — Ortopedia em sala inacessível ou andar alto   → operacional (alerta, não bloqueio)
"""
from __future__ import annotations

from src.models.schemas import Alocacao, Conflito, Grade, Restricao, Sala


def calcular_conflitos(
    grades: list[Grade],
    salas: list[Sala],
    restricoes: list[Restricao],
    alocacoes: list[Alocacao],
) -> list[Conflito]:
    """Retorna todos os conflitos detectados para o conjunto de dados informado."""
    resultado: list[Conflito] = []
    seq = 0

    def uid() -> str:
        nonlocal seq
        seq += 1
        return f"conf-{seq:04d}"

    sala_map  = {s.id: s for s in salas}
    grade_map = {g.id: g for g in grades}

    # ── C01/C02/C03: Status de sala inválido em alocação ─────────────────────
    for aloc in alocacoes:
        sala = sala_map.get(aloc.sala_id)
        if sala is None:
            continue
        if sala.status in ("reforma", "manutencao", "bloqueada"):
            tipo = {
                "reforma":    "sala_em_reforma",
                "manutencao": "sala_em_manutencao",
                "bloqueada":  "sala_bloqueada",
            }[sala.status]
            resultado.append(Conflito(
                id=uid(), tipo=tipo, gravidade="critico",
                descricao=f"Sala {sala.numero} ({sala.status}) está alocada em {aloc.dia_semana}/{aloc.turno}.",
                sala_id=sala.id, alocacao_id=aloc.id,
                dia_semana=aloc.dia_semana, turno=aloc.turno,
            ))

    # ── C04: Sala inexistente em alocação ─────────────────────────────────────
    for aloc in alocacoes:
        if aloc.sala_id not in sala_map:
            resultado.append(Conflito(
                id=uid(), tipo="sala_inexistente", gravidade="critico",
                descricao=f"Alocação {aloc.id} referencia sala inexistente '{aloc.sala_id}'.",
                alocacao_id=aloc.id,
            ))

    # ── C05: Grade inexistente em alocação ────────────────────────────────────
    for aloc in alocacoes:
        if aloc.grade_id not in grade_map:
            resultado.append(Conflito(
                id=uid(), tipo="grade_inexistente", gravidade="critico",
                descricao=f"Alocação {aloc.id} referencia grade inexistente '{aloc.grade_id}'.",
                alocacao_id=aloc.id,
            ))

    # ── C06: Dupla alocação (mesma sala, dia, turno) ──────────────────────────
    chave_aloc: dict[str, list[Alocacao]] = {}
    for aloc in alocacoes:
        chave = f"{aloc.sala_id}|{aloc.dia_semana}|{aloc.turno}"
        chave_aloc.setdefault(chave, []).append(aloc)

    for chave, grupo in chave_aloc.items():
        if len(grupo) > 1:
            sala_id, dia, turno = chave.split("|")
            sala = sala_map.get(sala_id)
            resultado.append(Conflito(
                id=uid(), tipo="dupla_alocacao", gravidade="critico",
                descricao=(
                    f"Sala {sala.numero if sala else sala_id} alocada para "
                    f"{len(grupo)} grades em {dia}/{turno}."
                ),
                sala_id=sala_id, dia_semana=dia, turno=turno,
            ))

    # ── C07: Grade sem sala associada ─────────────────────────────────────────
    grades_alocadas = {a.grade_id for a in alocacoes}
    for grade in grades:
        if grade.id not in grades_alocadas:
            resultado.append(Conflito(
                id=uid(), tipo="grade_sem_sala", gravidade="critico",
                descricao=(
                    f"Grade de {grade.especialidade} ({grade.profissional}) "
                    f"em {grade.dia_semana}/{grade.turno} não tem sala atribuída."
                ),
                grade_id=grade.id,
                especialidade=grade.especialidade,
                dia_semana=grade.dia_semana,
                turno=grade.turno,
            ))

    # ── C08/C09/C10: Regras por alocação x sala x grade ──────────────────────
    restricao_por_sala: dict[str, list[Restricao]] = {}
    for r in restricoes:
        restricao_por_sala.setdefault(r.sala_id, []).append(r)

    for aloc in alocacoes:
        sala  = sala_map.get(aloc.sala_id)
        grade = grade_map.get(aloc.grade_id)
        if sala is None or grade is None:
            continue

        # C08 — Especialidade em sala incompatível
        if (
            sala.especialidade_preferencial
            and sala.especialidade_preferencial.lower() not in ("geral", "")
            and sala.especialidade_preferencial.lower() != grade.especialidade.lower()
        ):
            resultado.append(Conflito(
                id=uid(), tipo="especialidade_incompativel", gravidade="operacional",
                descricao=(
                    f"Sala {sala.numero} é preferencial para {sala.especialidade_preferencial}, "
                    f"mas está alocada para {grade.especialidade} em {aloc.dia_semana}/{aloc.turno}."
                ),
                sala_id=sala.id, grade_id=grade.id, alocacao_id=aloc.id,
                especialidade=grade.especialidade,
                dia_semana=aloc.dia_semana, turno=aloc.turno,
            ))

        # C09 — Equipamento obrigatório ausente
        for restricao in restricao_por_sala.get(sala.id, []):
            if restricao.tipo == "equipamento_obrigatorio":
                if restricao.valor not in sala.equipamentos:
                    resultado.append(Conflito(
                        id=uid(), tipo="equipamento_ausente", gravidade="operacional",
                        descricao=(
                            f"Sala {sala.numero} não possui '{restricao.valor}' "
                            f"exigido para a alocação de {grade.especialidade}."
                        ),
                        sala_id=sala.id, grade_id=grade.id, alocacao_id=aloc.id,
                        especialidade=grade.especialidade,
                        dia_semana=aloc.dia_semana, turno=aloc.turno,
                    ))

        # C10 — Ortopedia em sala inacessível ou andar alto (alerta operacional)
        if grade.especialidade.lower() == "ortopedia":
            try:
                andar = int(sala.andar)
            except (ValueError, TypeError):
                andar = 0
            if not sala.acessibilidade or andar > 2:
                motivo = []
                if not sala.acessibilidade:
                    motivo.append("não acessível")
                if andar > 2:
                    motivo.append(f"andar {sala.andar}")
                resultado.append(Conflito(
                    id=uid(), tipo="ortopedia_acessibilidade", gravidade="operacional",
                    descricao=(
                        f"Ortopedia alocada em sala {sala.numero} ({', '.join(motivo)}). "
                        "Verificar viabilidade operacional."
                    ),
                    sala_id=sala.id, grade_id=grade.id, alocacao_id=aloc.id,
                    especialidade=grade.especialidade,
                    dia_semana=aloc.dia_semana, turno=aloc.turno,
                ))

    return resultado
