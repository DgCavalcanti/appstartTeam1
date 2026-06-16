from src.models.schemas import Conflito, DashboardResumo
from src.providers.interfaces.grade_provider_interface import GradeProviderInterface
from src.providers.interfaces.historico_provider_interface import AlocacaoSaaProviderInterface
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface
from src.services.conflito_service import calcular_conflitos


class DashboardController:

    def __init__(
        self,
        grade_provider: GradeProviderInterface,
        sala_provider: SalaProviderInterface,
        restricao_provider: RestricaoProviderInterface,
        alocacao_provider: AlocacaoSaaProviderInterface,
    ) -> None:
        self._grades     = grade_provider
        self._salas      = sala_provider
        self._restricoes = restricao_provider
        self._alocacoes  = alocacao_provider

    def resumo(self) -> DashboardResumo:
        salas     = self._salas.listar_salas()
        grades    = self._grades.listar_grades()
        alocacoes = self._alocacoes.listar_alocacoes()
        restricoes = self._restricoes.listar_restricoes()
        conflitos = calcular_conflitos(grades, salas, restricoes, alocacoes)

        return DashboardResumo(
            total_salas=len(salas),
            salas_disponiveis=sum(1 for s in salas if s.status == "disponivel"),
            salas_bloqueadas=sum(1 for s in salas if s.status == "bloqueada"),
            salas_reforma=sum(1 for s in salas if s.status in ("reforma", "manutencao")),
            total_conflitos=len(conflitos),
            conflitos_criticos=sum(1 for c in conflitos if c.gravidade == "critico"),
            total_grades=len(grades),
            total_alocacoes=len(alocacoes),
        )

    def conflitos(
        self,
        dia_semana: str | None = None,
        turno: str | None = None,
        especialidade: str | None = None,
    ) -> list[Conflito]:
        grades     = self._grades.listar_grades()
        salas      = self._salas.listar_salas()
        restricoes = self._restricoes.listar_restricoes()
        alocacoes  = self._alocacoes.listar_alocacoes()
        todos      = calcular_conflitos(grades, salas, restricoes, alocacoes)

        if dia_semana:
            todos = [c for c in todos if c.dia_semana and c.dia_semana.lower() == dia_semana.lower()]
        if turno:
            todos = [c for c in todos if c.turno and c.turno.lower() == turno.lower()]
        if especialidade:
            todos = [c for c in todos if c.especialidade and c.especialidade.lower() == especialidade.lower()]

        return todos
