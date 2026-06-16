"""
alocacao_controller.py — Controller de alocações SAA (MVP: sem alocação automática).

Responsabilidades:
  - Listar alocações com filtros
  - Processar ajuste manual (POST /api/alocacoes/ajustar)
  - Exigir justificativa quando há conflito crítico ou operacional
  - Registrar histórico após ajuste
"""
from __future__ import annotations

import uuid
from datetime import datetime

from src.models.schemas import (
    Alocacao,
    AjusteAlocacaoRequest,
    AjusteAlocacaoResponse,
    HistoricoAjuste,
)
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface
from src.providers.interfaces.historico_provider_interface import (
    AlocacaoSaaProviderInterface,
    HistoricoProviderInterface,
)
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface
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
