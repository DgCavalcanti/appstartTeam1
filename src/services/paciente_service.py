from src.repositories.interfaces.paciente_provider_interface import PacienteProviderInterface


class PacienteService:

    def __init__(self, provider: PacienteProviderInterface) -> None:
        self._provider = provider

    async def listar_pacientes(self) -> list[dict]:
        return await self._provider.listar_pacientes()

    async def obter_paciente_por_codigo(self, codigo: int) -> dict:
        return await self._provider.obter_paciente_por_codigo(codigo)
