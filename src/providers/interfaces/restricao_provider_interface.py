from abc import ABC, abstractmethod
from src.models.schemas import Restricao


class RestricaoProviderInterface(ABC):

    @abstractmethod
    def listar_restricoes(self) -> list[Restricao]: ...
