from abc import ABC, abstractmethod
from src.models.schemas import Alocacao, HistoricoAjuste


class AlocacaoSaaProviderInterface(ABC):

    @abstractmethod
    def listar_alocacoes(self) -> list[Alocacao]: ...

    @abstractmethod
    def buscar_alocacao(self, alocacao_id: str) -> Alocacao | None: ...

    @abstractmethod
    def atualizar_alocacao(self, alocacao: Alocacao) -> None: ...


class HistoricoProviderInterface(ABC):

    @abstractmethod
    def registrar(self, entrada: HistoricoAjuste) -> None: ...

    @abstractmethod
    def listar(self) -> list[HistoricoAjuste]: ...
