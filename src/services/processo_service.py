"""
processo_service.py — O orquestrador da máquina de estados das 6 etapas.

O documento pede um fluxo sequencial em que o gestor pode voltar a qualquer
etapa e ver o panorama atualizado. Este serviço é quem conhece a ordem das
etapas e propaga a invalidação: mexer nas grades, nas salas ou nas restrições
não apaga a alocação — apenas avisa que ela pode não valer mais.

Referência: SAA_Arquitetura.pdf, seção 7.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.processo import (
    CONCLUIDA,
    DESATUALIZADA,
    EM_ANDAMENTO,
    ETAPAS,
    PENDENTE,
    PREENCHIDA,
    PRIMEIRA_ETAPA,
    RASCUNHO,
    ULTIMA_ETAPA,
    etapa_por_numero,
    etapas_invalidadas_por,
)
from src.models.saa import Alocacao, AlocacaoEtapa

logger = logging.getLogger(__name__)

#: A etapa que executa o motor. Reexecutá-la regenera o resultado inteiro.
ETAPA_EXECUCAO = 5
#: A etapa de ajustes manuais, que edita o resultado da etapa 5.
ETAPA_AJUSTES = 6


class ProcessoService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # -- Consulta ----------------------------------------------------------

    def etapa(self, cenario: Alocacao, numero: int) -> AlocacaoEtapa:
        etapa_por_numero(numero)  # valida o intervalo
        for registro in cenario.etapas:
            if registro.numero == numero:
                return registro
        raise ValueError(
            f"cenário {cenario.id} não tem a etapa {numero} registrada"
        )

    def resumo(self, cenario: Alocacao) -> list[dict]:
        """As 6 etapas com nome e status — o que o stepper desenha."""
        por_numero = {e.numero: e for e in cenario.etapas}
        return [
            {
                "numero": etapa.numero,
                "chave": etapa.chave,
                "nome": etapa.nome,
                "status": (
                    por_numero[etapa.numero].status
                    if etapa.numero in por_numero
                    else PENDENTE
                ),
                "atual": etapa.numero == cenario.etapa_atual,
            }
            for etapa in ETAPAS
        ]

    # -- Transições --------------------------------------------------------

    async def registrar_alteracao(
        self, cenario: Alocacao, numero: int
    ) -> frozenset[int]:
        """
        Marca uma etapa como preenchida e propaga a invalidação.

        Devolve as etapas que ficaram desatualizadas, para a API avisar o gestor
        em vez de apagar o trabalho dele.
        """
        etapa_por_numero(numero)

        alvo = self.etapa(cenario, numero)
        alvo.status = PREENCHIDA
        alvo.atualizado_em = datetime.now(timezone.utc)

        invalidadas: set[int] = set()
        for candidata in etapas_invalidadas_por(numero):
            registro = self.etapa(cenario, candidata)
            # Só o que estava confiável pode ficar desatualizado; o que nunca
            # foi preenchido continua pendente.
            if registro.status == PREENCHIDA:
                registro.status = DESATUALIZADA
                registro.atualizado_em = datetime.now(timezone.utc)
                invalidadas.add(candidata)

        # Reexecutar o motor regenera o resultado inteiro, então os ajustes
        # manuais da etapa 6 deixam de existir. Não é "desatualizado" — é
        # trabalho que sumiu, e voltar a pendente descreve isso melhor.
        if numero == ETAPA_EXECUCAO:
            ajustes = self.etapa(cenario, ETAPA_AJUSTES)
            if ajustes.status != PENDENTE:
                ajustes.status = PENDENTE
                ajustes.atualizado_em = datetime.now(timezone.utc)

        self._atualizar_status(cenario)
        await self.sessao.flush()

        if invalidadas:
            logger.info(
                "cenário %d: etapa %d alterada → etapas %s desatualizadas",
                cenario.id,
                numero,
                sorted(invalidadas),
            )
        return frozenset(invalidadas)

    async def ir_para(self, cenario: Alocacao, numero: int) -> None:
        """Move o ponteiro do gestor. Não muda status de etapa nenhuma."""
        etapa_por_numero(numero)
        cenario.etapa_atual = numero
        await self.sessao.flush()

    async def concluir(self, cenario: Alocacao) -> None:
        """
        Fecha o cenário.

        Exige que a alocação tenha sido executada — sem isso não há o que
        concluir.
        """
        execucao = self.etapa(cenario, ETAPA_EXECUCAO)
        if execucao.status != PREENCHIDA:
            raise ValueError(
                "não é possível concluir: a alocação não foi executada "
                f"(etapa {ETAPA_EXECUCAO} está '{execucao.status}')"
            )
        cenario.status = CONCLUIDA
        cenario.etapa_atual = ULTIMA_ETAPA
        await self.sessao.flush()

    async def reabrir(self, cenario: Alocacao) -> None:
        """Tira o cenário de concluído para o gestor mexer de novo."""
        self._atualizar_status(cenario, forcar=True)
        await self.sessao.flush()

    # -- Auxiliares --------------------------------------------------------

    def _atualizar_status(self, cenario: Alocacao, forcar: bool = False) -> None:
        """
        Deriva o status do cenário a partir das etapas.

        Um cenário concluído volta a 'em andamento' assim que algo muda — do
        contrário ele ficaria marcado como fechado exibindo dados novos.
        """
        if cenario.status == CONCLUIDA and not forcar:
            cenario.status = EM_ANDAMENTO
            return

        avancou = any(
            e.status in (PREENCHIDA, DESATUALIZADA)
            for e in cenario.etapas
            if e.numero > PRIMEIRA_ETAPA
        )
        cenario.status = EM_ANDAMENTO if avancou else RASCUNHO
