from abc import ABC, abstractmethod
from src.models.schemas import Sala


class SalaProviderInterface(ABC):

    @abstractmethod
    def listar_salas(self) -> list[Sala]: ...

    @abstractmethod
    def buscar_sala(self, sala_id: str) -> Sala | None: ...
