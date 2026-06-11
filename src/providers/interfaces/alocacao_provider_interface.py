"""
alocacao_provider_interface.py — Contrato do Provider de Alocação

Define o que qualquer implementação (CSV, banco, AGHU) deve fornecer
ao controller. O controller depende desta interface, nunca da implementação.
"""
from abc import ABC, abstractmethod

from src.models.schemas import Alocacao, Grade, Sala


class AlocacaoProviderInterface(ABC):

    @abstractmethod
    def listar_grades(self) -> list[Grade]:
        """Retorna todas as grades cadastradas."""
        ...

    @abstractmethod
    def listar_salas(self) -> list[Sala]:
        """Retorna todas as salas cadastradas."""
        ...

    @abstractmethod
    def listar_historico(self) -> list[Alocacao]:
        """
        Retorna o histórico de alocações anteriores.
        Usado pelo motor para calcular preferência de profissional por sala.
        """
        ...

    @abstractmethod
    def salvar_alocacoes(self, alocacoes: list[Alocacao]) -> None:
        """
        Persiste as alocações geradas pelo motor.
        No MVP grava em SQLite; no futuro pode gravar no AGHU.
        """
        ...
