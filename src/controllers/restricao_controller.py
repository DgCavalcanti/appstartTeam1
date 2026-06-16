from src.models.schemas import Restricao
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface


class RestricaoController:

    def __init__(self, provider: RestricaoProviderInterface) -> None:
        self._provider = provider

    def listar_restricoes(self) -> list[Restricao]:
        return self._provider.listar_restricoes()
