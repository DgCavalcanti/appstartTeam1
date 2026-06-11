"""
alocacao_controller.py — Controller de Alocação Automática

Orquestra o fluxo:
  1. Recebe dia_semana e turno do router
  2. Carrega dados via provider
  3. Aciona o motor de alocação
  4. Converte o resultado em Alocacoes e persiste
  5. Retorna o resultado ao router

Não contém lógica de negócio — esta fica no alocacao_engine.
Não acessa CSV ou banco diretamente — isto fica no provider.
"""
from __future__ import annotations

import logging
from datetime import datetime

from src.models.schemas import Alocacao, ResultadoMotor
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface
from src.services.alocacao_engine import alocar

logger = logging.getLogger(__name__)


class AlocacaoController:
    """
    Recebe o provider por injeção de dependência.
    No FastAPI, instanciado via Depends() no router.
    """

    def __init__(self, provider: AlocacaoProviderInterface) -> None:
        self.provider = provider

    # ------------------------------------------------------------------
    # Alocação automática
    # ------------------------------------------------------------------

    def alocar_automaticamente(self, dia_semana: str, turno: str) -> ResultadoMotor:
        """
        Executa o motor de alocação para o dia/turno solicitado e persiste o resultado.

        Parâmetros:
            dia_semana — ex: "segunda", "terca", "quarta"
            turno      — "manha" | "tarde"

        Retorna:
            ResultadoMotor com alocações geradas e grades sem alocação
        """
        logger.info("Alocação automática solicitada: %s %s", dia_semana, turno)

        # 1. Carrega dados
        try:
            grades   = self.provider.listar_grades()
            salas    = self.provider.listar_salas()
            historico = self.provider.listar_historico()
        except (FileNotFoundError, ValueError) as e:
            logger.error("Falha ao carregar dados para alocação: %s", e)
            raise

        # 2. Aciona o motor
        resultado = alocar(
            dia_semana=dia_semana,
            turno=turno,
            grades=grades,
            salas=salas,
            historico=historico,
        )

        # 3. Converte resultado em Alocacoes e persiste
        alocacoes_para_salvar = self._converter_para_alocacoes(resultado)
        if alocacoes_para_salvar:
            self.provider.salvar_alocacoes(alocacoes_para_salvar)

        logger.info(
            "Alocação concluída: %d alocadas | %d sem alocação",
            sum(1 for a in resultado.alocacoes if a.alocado),
            len(resultado.grades_sem_alocacao),
        )

        return resultado

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _converter_para_alocacoes(self, resultado: ResultadoMotor) -> list[Alocacao]:
        """
        Converte ResultadoAlocacao (saída do motor) em objetos Alocacao
        prontos para persistência.
        Gera um registro por sala alocada (grades com múltiplas salas geram N registros).
        """
        alocacoes: list[Alocacao] = []
        # ID sintético baseado em timestamp para evitar colisão no MVP
        base_id = int(datetime.now().timestamp() * 1000)

        for i, resultado_alocacao in enumerate(resultado.alocacoes):
            if not resultado_alocacao.alocado:
                continue
            for j, id_sala in enumerate(resultado_alocacao.salas_alocadas):
                alocacoes.append(Alocacao(
                    id=base_id + (i * 100) + j,
                    id_grade=resultado_alocacao.id_grade,
                    id_sala=id_sala,
                    dia_semana=resultado.dia_semana,
                    turno=resultado.turno,
                    status="alocado",
                ))

        return alocacoes
