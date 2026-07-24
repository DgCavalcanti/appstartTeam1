"""
restricoes_service.py — Etapa 4: obrigatoriedades e preferências.

A distinção entre as duas é o que define o caráter do algoritmo:

- **Obrigatória** é uma trava. A clínica vai para aquele pavimento mesmo que
  isso deixe grades sem sala. É a única coisa capaz de gerar sobra.
- **Preferencial** é um puxão. Entra como afinidade e cede quando o pavimento
  não comporta a clínica inteira — um desejo nunca faz ninguém perder
  atendimento havendo espaço ao lado.

Referência: SAA_Arquitetura.pdf, seções 7 e 8.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entidades import OBRIGATORIO, PREFERENCIAL
from src.models.saa import Alocacao, Restricao
from src.services.processo_service import ProcessoService

logger = logging.getLogger(__name__)

ETAPA_RESTRICOES = 4


class RestricoesService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.processo = ProcessoService(sessao)

    def listar(self, cenario: Alocacao) -> list[dict]:
        unidades = {u.id: u.unidade_nome for u in cenario.unidades}
        pavimentos = {p.id: p.nome_completo for p in cenario.pavimentos}
        return [
            {
                "id": r.id,
                "unidade_id": r.alocacao_unidade_id,
                "unidade": unidades.get(r.alocacao_unidade_id, "?"),
                "pavimento_id": r.pavimento_id,
                "pavimento": pavimentos.get(r.pavimento_id, "?"),
                "tipo": r.tipo,
            }
            for r in cenario.restricoes
        ]

    async def definir(
        self, cenario: Alocacao, unidade_id: int, pavimento_id: int, tipo: str
    ) -> Restricao:
        """
        Cria ou substitui uma restrição.

        Uma unidade só pode ter uma obrigatoriedade: ela fica num pavimento só
        na semana inteira, então duas travas seriam contraditórias. Definir uma
        nova substitui a anterior em vez de acumular um conflito silencioso.
        """
        if tipo not in (OBRIGATORIO, PREFERENCIAL):
            raise ValueError(
                f"tipo inválido: {tipo!r}. Esperado {OBRIGATORIO!r} ou {PREFERENCIAL!r}"
            )
        self._validar_pertence(cenario, unidade_id, pavimento_id)

        if tipo == OBRIGATORIO:
            anteriores = [
                r
                for r in cenario.restricoes
                if r.alocacao_unidade_id == unidade_id and r.tipo == OBRIGATORIO
            ]
            for antiga in anteriores:
                cenario.restricoes.remove(antiga)
                await self.sessao.delete(antiga)

        existente = next(
            (
                r
                for r in cenario.restricoes
                if r.alocacao_unidade_id == unidade_id
                and r.pavimento_id == pavimento_id
                and r.tipo == tipo
            ),
            None,
        )
        if existente is not None:
            return existente

        restricao = Restricao(
            alocacao_id=cenario.id,
            alocacao_unidade_id=unidade_id,
            pavimento_id=pavimento_id,
            tipo=tipo,
        )
        self.sessao.add(restricao)
        cenario.restricoes.append(restricao)

        await self.processo.registrar_alteracao(cenario, ETAPA_RESTRICOES)
        logger.info(
            "cenário %d: unidade %d marcada como %s no pavimento %d",
            cenario.id,
            unidade_id,
            tipo,
            pavimento_id,
        )
        return restricao

    async def remover(self, cenario: Alocacao, restricao_id: int) -> bool:
        restricao = next(
            (r for r in cenario.restricoes if r.id == restricao_id), None
        )
        if restricao is None:
            return False

        cenario.restricoes.remove(restricao)
        await self.sessao.delete(restricao)
        await self.processo.registrar_alteracao(cenario, ETAPA_RESTRICOES)
        return True

    @staticmethod
    def _validar_pertence(
        cenario: Alocacao, unidade_id: int, pavimento_id: int
    ) -> None:
        if not any(u.id == unidade_id for u in cenario.unidades):
            raise ValueError(
                f"unidade {unidade_id} não pertence ao cenário {cenario.id}"
            )
        if not any(p.id == pavimento_id for p in cenario.pavimentos):
            raise ValueError(
                f"pavimento {pavimento_id} não pertence ao cenário {cenario.id}"
            )
