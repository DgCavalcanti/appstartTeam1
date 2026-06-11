"""
alocacao.py — Router FastAPI do módulo de Alocação

Expõe os endpoints de alocação automática.
Não contém regra de negócio — delega ao AlocacaoController.

Endpoints:
  POST /api/alocacoes/automatica   — executa o motor de alocação para dia/turno
  GET  /api/alocacoes              — lista alocações (histórico)
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.alocacao_controller import AlocacaoController
from src.models.schemas import ResultadoMotor
from src.providers.implementations.alocacao_csv_provider import AlocacaoCsvProvider
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/alocacoes", tags=["Alocações"])

# Valores válidos aceitos pela API
DIAS_VALIDOS   = {"segunda", "terca", "quarta", "quinta", "sexta"}
TURNOS_VALIDOS = {"manha", "tarde"}

# ---------------------------------------------------------------------------
# Injeção de dependência do provider
# ---------------------------------------------------------------------------

def get_provider() -> AlocacaoProviderInterface:
    """
    Instancia o provider CSV com os caminhos padrão.
    Em testes, substituir via app.dependency_overrides[get_provider].
    """
    return AlocacaoCsvProvider(
        caminho_grades=Path("data/grades.csv"),
        caminho_salas=Path("data/salas.csv"),
        caminho_alocacoes=Path("data/alocacoes.csv"),
        caminho_db=Path("data/historico.db"),
    )


def get_controller(
    provider: AlocacaoProviderInterface = Depends(get_provider),
) -> AlocacaoController:
    return AlocacaoController(provider)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/automatica",
    response_model=ResultadoMotor,
    status_code=status.HTTP_200_OK,
    summary="Executar alocação automática",
    description=(
        "Executa o motor de alocação para o dia e turno informados. "
        "Retorna as alocações geradas e as grades que não puderam ser alocadas."
    ),
)
def alocar_automaticamente(
    dia_semana: str = Query(
        ...,
        description="Dia da semana (segunda | terca | quarta | quinta | sexta)",
        examples=["segunda"],
    ),
    turno: str = Query(
        ...,
        description="Turno (manha | tarde)",
        examples=["manha"],
    ),
    controller: AlocacaoController = Depends(get_controller),
) -> ResultadoMotor:
    """
    POST /api/alocacoes/automatica?dia_semana=segunda&turno=manha

    Protegido por JWT via Depends(auth_handler.decode_token) — a ser adicionado
    quando a autenticação estiver integrada (RNF002).
    """
    # Valida parâmetros antes de acionar o motor
    dia_normalizado   = dia_semana.strip().lower()
    turno_normalizado = turno.strip().lower()

    if dia_normalizado not in DIAS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"dia_semana inválido: '{dia_semana}'. Valores aceitos: {sorted(DIAS_VALIDOS)}",
        )

    if turno_normalizado not in TURNOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"turno inválido: '{turno}'. Valores aceitos: {sorted(TURNOS_VALIDOS)}",
        )

    try:
        resultado = controller.alocar_automaticamente(dia_normalizado, turno_normalizado)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Arquivo de dados não encontrado: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dados inválidos nos arquivos CSV: {e}",
        )

    return resultado


@router.get(
    "",
    summary="Listar histórico de alocações",
    description="Retorna o histórico de alocações persistidas no banco.",
)
def listar_alocacoes(
    dia_semana: str | None = Query(None, description="Filtrar por dia da semana"),
    turno: str | None      = Query(None, description="Filtrar por turno"),
    provider: AlocacaoProviderInterface = Depends(get_provider),
):
    """GET /api/alocacoes?dia_semana=segunda&turno=manha"""
    historico = provider.listar_historico()

    if dia_semana:
        historico = [a for a in historico if a.dia_semana.lower() == dia_semana.lower()]
    if turno:
        historico = [a for a in historico if a.turno.lower() == turno.lower()]

    return historico
