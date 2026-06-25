"""
alocacao_controller.py — Controller de alocações SAA.

Responsabilidades:
  - Listar alocações com filtros
  - Criar a primeira alocação de uma grade (POST /api/alocacoes)
  - Executar alocação automática por dia/turno via motor de regras
    (POST /api/alocacoes/automatica)
  - Processar ajuste manual (POST /api/alocacoes/ajustar)
  - Exigir justificativa quando há conflito crítico ou operacional
  - Registrar histórico após criação/ajuste/alocação automática
"""
from __future__ import annotations

import uuid
from datetime import datetime

from src.models.schemas import (
    Alocacao,
    AlocacaoAutomaticaRequest,
    AlocacaoAutomaticaResponse,
    AjusteAlocacaoRequest,
    AjusteAlocacaoResponse,
    CriarAlocacaoRequest,
    CriarAlocacaoResponse,
    HistoricoAjuste,
)
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface
from src.providers.interfaces.historico_provider_interface import (
    AlocacaoSaaProviderInterface,
    HistoricoProviderInterface,
)
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface
from src.services.alocacao_engine import _normalizar_texto, alocar
from src.services.conflito_service import calcular_conflitos


class AlocacaoController:

    def __init__(
        self,
        alocacao_provider: AlocacaoSaaProviderInterface,
        grade_provider: GradeProviderInterface,
        sala_provider: SalaProviderInterface,
        restricao_provider: RestricaoProviderInterface,
        historico_provider: HistoricoProviderInterface,
    ) -> None:
        self._alocacoes  = alocacao_provider
        self._grades     = grade_provider
        self._salas      = sala_provider
        self._restricoes = restricao_provider
        self._historico  = historico_provider

    def listar_alocacoes(
        self,
        dia_semana: str | None = None,
        turno: str | None = None,
    ) -> list[Alocacao]:
        alocacoes = self._alocacoes.listar_alocacoes()
        if dia_semana:
            alocacoes = [a for a in alocacoes if a.dia_semana.lower() == dia_semana.lower()]
        if turno:
            alocacoes = [a for a in alocacoes if a.turno.lower() == turno.lower()]
        return alocacoes

    def criar_alocacao(self, req: CriarAlocacaoRequest, usuario: str = "sistema") -> CriarAlocacaoResponse:
        """Cria a primeira alocação de sala para uma grade que ainda não tem
        nenhuma (caminho que faltava no MVP — ver auditoria: antes disso o
        frontend só empurrava a alocação localmente, sem persistir no
        backend, e por isso ela desaparecia ao recarregar o Painel SAA)."""
        # 1. Verificar existência da grade exatamente nesse dia/turno —
        # grade_id por si só pode ser ambíguo (grade recorrente em mais de
        # um dia), então a busca usa a tripla (id, dia_semana, turno).
        grade = next(
            (
                g for g in self._grades.listar_grades()
                if g.id == req.grade_id
                and g.dia_semana == req.dia_semana
                and g.turno == req.turno
            ),
            None,
        )
        if grade is None:
            raise ValueError(
                f"Grade '{req.grade_id}' ({req.dia_semana}/{req.turno}) não encontrada."
            )

        sala_nova = self._salas.buscar_sala(req.sala_id)
        if sala_nova is None:
            raise ValueError(f"Sala '{req.sala_id}' não encontrada.")

        # 2. Garantir que essa grade ainda não tem alocação — se já tiver,
        # quem chama deve usar o ajuste de sala (POST /api/alocacoes/ajustar).
        alocacoes = self._alocacoes.listar_alocacoes()
        existente = next(
            (
                a for a in alocacoes
                if a.grade_id == req.grade_id
                and a.dia_semana == req.dia_semana
                and a.turno == req.turno
            ),
            None,
        )
        if existente is not None:
            raise ValueError(
                f"A grade '{req.grade_id}' ({req.dia_semana}/{req.turno}) já possui "
                f"uma alocação (sala '{existente.sala_id}'). Use o ajuste de sala "
                "em vez de criar uma nova."
            )

        # 3. Simular a nova alocação para calcular conflitos
        grades     = self._grades.listar_grades()
        salas      = self._salas.listar_salas()
        restricoes = self._restricoes.listar_restricoes()
        nova_alocacao = Alocacao(
            id=str(uuid.uuid4()),
            grade_id=req.grade_id,
            sala_id=req.sala_id,
            dia_semana=req.dia_semana,
            turno=req.turno,
        )
        alocacoes_simuladas = alocacoes + [nova_alocacao]
        conflitos_depois = calcular_conflitos(grades, salas, restricoes, alocacoes_simuladas)
        conflitos_depois_aloc = [
            c for c in conflitos_depois
            if c.alocacao_id == nova_alocacao.id or c.sala_id == req.sala_id
        ]

        # 4. Exigir justificativa se houver conflito crítico ou operacional
        tem_conflito_relevante = any(
            c.gravidade in ("critico", "operacional") for c in conflitos_depois_aloc
        )
        if tem_conflito_relevante and not req.justificativa:
            raise ValueError(
                "Justificativa obrigatória quando há conflito crítico ou operacional na sala escolhida."
            )

        # 5. Persistir
        self._alocacoes.atualizar_alocacao(nova_alocacao)

        # 6. Registrar histórico (sem sala anterior — é uma criação, não um ajuste)
        entrada_historico = HistoricoAjuste(
            id=str(uuid.uuid4()),
            alocacao_id=nova_alocacao.id,
            sala_anterior_id="",
            sala_nova_id=req.sala_id,
            data_hora=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            usuario=usuario,
            justificativa=req.justificativa,
            conflitos_antes=[],
            conflitos_depois=conflitos_depois_aloc,
        )
        self._historico.registrar(entrada_historico)

        return CriarAlocacaoResponse(
            alocacao=nova_alocacao,
            conflitos_depois=conflitos_depois_aloc,
            historico=entrada_historico,
        )

    def alocar_automaticamente(
        self,
        req: AlocacaoAutomaticaRequest,
        usuario: str = "sistema",
    ) -> AlocacaoAutomaticaResponse:
        grades = self._grades.listar_grades()
        salas = self._salas.listar_salas()
        restricoes = self._restricoes.listar_restricoes()
        alocacoes_antes = self._alocacoes.listar_alocacoes()

        # Mapa grade_id -> grade nessa ocorrência (dia/turno normalizados).
        # CORRIGIDO: usado para persistir dia_semana/turno com a grafia
        # canônica da grade (ex.: "Segunda"/"Manhã"), não o texto bruto da
        # requisição. Sem isso, uma chamada com "segunda"/"manha" (válida,
        # pois o motor casa por normalização) gravava a alocação com essa
        # grafia — e o Painel/regra C07 comparam dia_semana/turno por
        # igualdade exata, então a alocação "desaparecia" para eles mesmo
        # tendo sido criada com sucesso.
        grade_por_id = {
            g.id: g
            for g in grades
            if _normalizar_texto(g.dia_semana) == _normalizar_texto(req.dia_semana)
            and _normalizar_texto(g.turno) == _normalizar_texto(req.turno)
        }

        def mesma_ocorrencia(a: Alocacao, grade_id: str) -> bool:
            return (
                a.grade_id == grade_id
                and _normalizar_texto(a.dia_semana) == _normalizar_texto(req.dia_semana)
                and _normalizar_texto(a.turno) == _normalizar_texto(req.turno)
            )

        ocupadas_existentes = {
            a.sala_id for a in alocacoes_antes
            if _normalizar_texto(a.dia_semana) == _normalizar_texto(req.dia_semana)
            and _normalizar_texto(a.turno) == _normalizar_texto(req.turno)
        }
        salas_disponiveis = salas if req.sobrescrever else [
            sala for sala in salas if sala.id not in ocupadas_existentes
        ]

        resultado_motor = alocar(
            dia_semana=req.dia_semana,
            turno=req.turno,
            grades=grades,
            salas=salas_disponiveis,
            historico=alocacoes_antes,
        )

        persistidas: list[Alocacao] = []
        sem_alocacao = set(resultado_motor.grades_sem_alocacao)

        for resultado in resultado_motor.alocacoes:
            existentes = [
                a for a in alocacoes_antes
                if mesma_ocorrencia(a, resultado.grade_id)
            ]

            if existentes and not req.sobrescrever:
                continue

            if not resultado.alocado or not resultado.salas_alocadas:
                sem_alocacao.add(resultado.grade_id)
                continue

            grade = grade_por_id.get(resultado.grade_id)
            dia_semana_persistido = grade.dia_semana if grade else req.dia_semana
            turno_persistido = grade.turno if grade else req.turno

            for idx, sala_id in enumerate(resultado.salas_alocadas):
                alocacao_id = (
                    existentes[idx].id
                    if idx < len(existentes)
                    else (
                        f"AUTO-{resultado.grade_id}-"
                        f"{_normalizar_texto(req.dia_semana).replace(' ', '-')}-"
                        f"{_normalizar_texto(req.turno).replace(' ', '-')}-{idx + 1}"
                    )
                )
                nova = Alocacao(
                    id=alocacao_id,
                    grade_id=resultado.grade_id,
                    sala_id=sala_id,
                    dia_semana=dia_semana_persistido,
                    turno=turno_persistido,
                )
                self._alocacoes.atualizar_alocacao(nova)
                persistidas.append(nova)

                sala_anterior_id = existentes[idx].sala_id if idx < len(existentes) else ""
                self._historico.registrar(HistoricoAjuste(
                    id=str(uuid.uuid4()),
                    alocacao_id=nova.id,
                    sala_anterior_id=sala_anterior_id,
                    sala_nova_id=sala_id,
                    data_hora=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                    usuario=usuario,
                    justificativa="Alocacao automatica",
                    conflitos_antes=[],
                    conflitos_depois=[],
                ))

        alocacoes_depois = self._alocacoes.listar_alocacoes()
        conflitos = calcular_conflitos(grades, salas, restricoes, alocacoes_depois)

        return AlocacaoAutomaticaResponse(
            dia_semana=req.dia_semana,
            turno=req.turno,
            total_grades=len(resultado_motor.alocacoes),
            total_alocadas=sum(1 for a in resultado_motor.alocacoes if a.alocado),
            total_sem_alocacao=len(sem_alocacao),
            alocacoes_persistidas=persistidas,
            grades_sem_alocacao=sorted(sem_alocacao),
            conflitos=conflitos,
        )

    def ajustar_alocacao(self, req: AjusteAlocacaoRequest, usuario: str = "sistema") -> AjusteAlocacaoResponse:
        # 1. Verificar existência
        alocacao = self._alocacoes.buscar_alocacao(req.alocacao_id)
        if alocacao is None:
            raise ValueError(f"Alocação '{req.alocacao_id}' não encontrada.")

        sala_nova = self._salas.buscar_sala(req.nova_sala_id)
        if sala_nova is None:
            raise ValueError(f"Sala '{req.nova_sala_id}' não encontrada.")

        # 2. Carregar contexto atual
        grades     = self._grades.listar_grades()
        salas      = self._salas.listar_salas()
        restricoes = self._restricoes.listar_restricoes()
        alocacoes  = self._alocacoes.listar_alocacoes()

        # 3. Conflitos ANTES
        conflitos_antes = calcular_conflitos(grades, salas, restricoes, alocacoes)
        conflitos_antes_aloc = [
            c for c in conflitos_antes
            if c.alocacao_id == req.alocacao_id
            or c.sala_id == alocacao.sala_id
        ]

        # 4. Simular mudança
        sala_anterior_id = alocacao.sala_id
        alocacao_simulada = Alocacao(
            id=alocacao.id,
            grade_id=alocacao.grade_id,
            sala_id=req.nova_sala_id,
            dia_semana=alocacao.dia_semana,
            turno=alocacao.turno,
        )
        alocacoes_simuladas = [
            alocacao_simulada if a.id == alocacao.id else a
            for a in alocacoes
        ]
        conflitos_depois = calcular_conflitos(grades, salas, restricoes, alocacoes_simuladas)
        conflitos_depois_aloc = [
            c for c in conflitos_depois
            if c.alocacao_id == req.alocacao_id
            or c.sala_id == req.nova_sala_id
        ]

        # 5. Exigir justificativa se houver conflito crítico ou operacional após a mudança
        tem_conflito_relevante = any(
            c.gravidade in ("critico", "operacional") for c in conflitos_depois_aloc
        )
        if tem_conflito_relevante and not req.justificativa:
            raise ValueError(
                "Justificativa obrigatória quando há conflito crítico ou operacional na nova sala."
            )

        # 6. Persistir ajuste
        self._alocacoes.atualizar_alocacao(alocacao_simulada)

        # 7. Registrar histórico
        entrada_historico = HistoricoAjuste(
            id=str(uuid.uuid4()),
            alocacao_id=req.alocacao_id,
            sala_anterior_id=sala_anterior_id,
            sala_nova_id=req.nova_sala_id,
            data_hora=datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            usuario=usuario,
            justificativa=req.justificativa,
            conflitos_antes=conflitos_antes_aloc,
            conflitos_depois=conflitos_depois_aloc,
        )
        self._historico.registrar(entrada_historico)

        return AjusteAlocacaoResponse(
            alocacao=alocacao_simulada,
            conflitos_depois=conflitos_depois_aloc,
            historico=entrada_historico,
        )

    def listar_historico(self) -> list[HistoricoAjuste]:
        return self._historico.listar()
