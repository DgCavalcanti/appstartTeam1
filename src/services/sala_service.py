from src.models.schemas import Sala
from src.repositories.interfaces.sala_provider_interface import SalaProviderInterface


class SalaService:

    def __init__(self, provider: SalaProviderInterface) -> None:
        self._provider = provider

    def listar_salas(
        self,
        bloco: str | None = None,
        status: str | None = None,
        especialidade: str | None = None,
    ) -> list[Sala]:
        salas = self._provider.listar_salas()
        if bloco:
            salas = [s for s in salas if s.bloco.lower() == bloco.lower()]
        if status:
            salas = [s for s in salas if s.status.lower() == status.lower()]
        if especialidade:
            salas = [
                s for s in salas
                if s.especialidade_preferencial
                and s.especialidade_preferencial.lower() == especialidade.lower()
            ]
        return salas

    def buscar_sala(self, sala_id: str) -> Sala | None:
        return self._provider.buscar_sala(sala_id)
