"""
Camada de serviços — os casos de uso.

Orquestra cada operação do gestor: coordena domínio e repositórios e controla a
transição entre as 6 etapas. Não fala HTTP e não escreve SQL.
"""

from src.services.alocacao_service import AlocacaoService
from src.services.grades_service import GradesService
from src.services.panorama_service import PanoramaService
from src.services.processo_service import ProcessoService
from src.services.restricoes_service import RestricoesService

__all__ = [
    "AlocacaoService",
    "GradesService",
    "PanoramaService",
    "ProcessoService",
    "RestricoesService",
]
