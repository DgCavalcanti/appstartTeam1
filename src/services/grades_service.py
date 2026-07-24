"""
grades_service.py — Etapa 2: validar e ajustar as grades.

O gestor confere a demanda que veio da importação, corrige o que precisar e
decide quais unidades participam da alocação.

Referência: SAA_Arquitetura.pdf, seções 6 e 7.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entidades import NUM_TURNOS, TURNOS, indice_turno
from src.models.saa import Alocacao, AlocacaoUnidade, GradeDemanda
from src.services.processo_service import ProcessoService

logger = logging.getLogger(__name__)

ETAPA_GRADES = 2


class GradesService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.processo = ProcessoService(sessao)

    def ler(self, cenario: Alocacao) -> list[dict]:
        """A planilha da etapa 2: uma linha por unidade, 10 colunas de turno."""
        linhas = []
        for unidade in cenario.unidades:
            demanda = [0] * NUM_TURNOS
            for item in unidade.demandas:
                demanda[indice_turno(item.dia_semana, item.turno)] = item.quantidade

            linhas.append(
                {
                    "id": unidade.id,
                    "nome": unidade.unidade_nome,
                    "participa": unidade.participa,
                    "demanda": demanda,
                    "total": sum(demanda),
                    "pico": max(demanda) if demanda else 0,
                    # Os ~7% de casos de profissional em duas clínicas no mesmo
                    # turno. A etapa 2 destaca para o gestor conferir.
                    "slots_em_revisao": sum(1 for s in unidade.slots if s.revisar),
                }
            )
        return linhas

    async def editar_demanda(
        self, cenario: Alocacao, unidade_id: int, dia: str, turno: str, quantidade: int
    ) -> GradeDemanda:
        """
        Ajusta a contagem de grades de um turno.

        O ajuste é soberano: pode passar do que veio do AGHU. A importação é um
        ponto de partida, não um teto — o gestor conhece exceções que a
        exportação não registra.
        """
        if quantidade < 0:
            raise ValueError("a quantidade não pode ser negativa")
        indice_turno(dia, turno)  # valida contra a malha de 10 turnos

        unidade = self._unidade(cenario, unidade_id)
        registro = next(
            (
                d
                for d in unidade.demandas
                if d.dia_semana == dia and d.turno == turno
            ),
            None,
        )

        if registro is None:
            registro = GradeDemanda(
                alocacao_unidade_id=unidade.id,
                dia_semana=dia,
                turno=turno,
                quantidade=quantidade,
            )
            self.sessao.add(registro)
            unidade.demandas.append(registro)
        else:
            registro.quantidade = quantidade

        await self.processo.registrar_alteracao(cenario, ETAPA_GRADES)
        return registro

    async def definir_participacao(
        self, cenario: Alocacao, unidade_id: int, participa: bool
    ) -> AlocacaoUnidade:
        """Tira ou devolve uma unidade à alocação."""
        unidade = self._unidade(cenario, unidade_id)
        unidade.participa = participa
        if not participa:
            # Sair da alocação significa não ocupar pavimento nenhum.
            unidade.pavimento_alocado_id = None

        await self.processo.registrar_alteracao(cenario, ETAPA_GRADES)
        logger.info(
            "cenário %d: %s agora %s",
            cenario.id,
            unidade.unidade_nome,
            "participa" if participa else "não participa",
        )
        return unidade

    def totais_por_turno(self, cenario: Alocacao) -> list[int]:
        """Rodapé da planilha: a demanda somada de todas as unidades ativas."""
        totais = [0] * NUM_TURNOS
        for unidade in cenario.unidades:
            if not unidade.participa:
                continue
            for item in unidade.demandas:
                totais[indice_turno(item.dia_semana, item.turno)] += item.quantidade
        return totais

    @staticmethod
    def _unidade(cenario: Alocacao, unidade_id: int) -> AlocacaoUnidade:
        unidade = next((u for u in cenario.unidades if u.id == unidade_id), None)
        if unidade is None:
            raise ValueError(
                f"unidade {unidade_id} não pertence ao cenário {cenario.id}"
            )
        return unidade
