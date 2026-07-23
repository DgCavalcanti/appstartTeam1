from src.models.schemas import Restricao
from src.repositories.interfaces.restricao_provider_interface import RestricaoProviderInterface


class RestricaoService:

    def __init__(self, provider: RestricaoProviderInterface) -> None:
        self._provider = provider

    def listar_restricoes(self) -> list[Restricao]:
        return self._provider.listar_restricoes()
