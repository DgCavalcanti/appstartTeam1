"""
alocacao.py — Router FastAPI do módulo de Alocação

Expõe os endpoints de alocação automática.
Não contém regra de negócio — delega ao AlocacaoController.

Endpoints:
  POST /api/alocacoes/automatica   — executa o motor de alocação para dia/turno
  GET  /api/alocacoes              — lista alocações (histórico)
  GET  /api/grades                 — lista grades
  GET  /api/salas                  — lista salas
  GET  /api/restricoes             — lista restrições
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.alocacao_controller import AlocacaoController
from src.models.schemas import ResultadoMotor, Grade, Sala, Restricao
from src.providers.implementations.alocacao_csv_provider import AlocacaoCsvProvider
from src.providers.interfaces.alocacao_provider_interface import AlocacaoProviderInterface
from src.auth.auth import auth_handler

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
    token: dict = Depends(auth_handler.decode_token),
):
    """
    POST /api/alocacoes/automatica?dia_semana=segunda&turno=manha

    Protegido por JWT (RNF002). Token obrigatório via header Authorization: Bearer <token>
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

    # Monta alocacoes_criadas: uma entrada por sala alocada, no formato que o frontend espera
    alocacoes_criadas = []
    base_id = int(__import__('datetime').datetime.now().timestamp() * 1000)
    contador = 0
    for ra in resultado.alocacoes:
        if not ra.alocado or not ra.salas_alocadas:
            continue
        for id_sala in ra.salas_alocadas:
            alocacoes_criadas.append({
                "id": str(base_id + contador),
                "grade_id": str(ra.id_grade),
                "sala_id": str(id_sala),
                "dia_semana": resultado.dia_semana,
                "turno": resultado.turno,
            })
            contador += 1

    grades_nao_alocadas = [
        {
            "id_grade": ra.id_grade,
            "especialidade": ra.especialidade,
            "profissional": ra.profissional,
        }
        for ra in resultado.alocacoes if not ra.alocado
    ]

    return {
        "alocacoes_criadas": alocacoes_criadas,
        "grades_nao_alocadas": grades_nao_alocadas,
        "conflitos_detectados": [],
    }


@router.get(
    "",
    summary="Listar histórico de alocações",
    description="Retorna o histórico de alocações persistidas no banco.",
)
def listar_alocacoes(
    dia_semana: str | None = Query(None, description="Filtrar por dia da semana"),
    turno: str | None      = Query(None, description="Filtrar por turno"),
    provider: AlocacaoProviderInterface = Depends(get_provider),
    token: dict = Depends(auth_handler.decode_token),
):
    """GET /api/alocacoes?dia_semana=segunda&turno=manha

    Protegido por JWT (RNF002).
    """
    historico = provider.listar_historico()

    if dia_semana:
        historico = [a for a in historico if a.dia_semana.lower() == dia_semana.lower()]
    if turno:
        historico = [a for a in historico if a.turno.lower() == turno.lower()]

    return historico


@router.get(
    "/../grades",
    response_model=list[Grade],
    summary="Listar grades",
    description="Retorna a lista de todas as grades.",
)
def listar_grades(
    dia_semana: str | None = Query(None, description="Filtrar por dia da semana"),
    turno: str | None = Query(None, description="Filtrar por turno"),
    provider: AlocacaoProviderInterface = Depends(get_provider),
    token: dict = Depends(auth_handler.decode_token),
) -> list[Grade]:
    """GET /api/grades?dia_semana=segunda&turno=manha

    Protegido por JWT (RNF002).
    """
    try:
        grades = provider.listar_grades()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Arquivo de grades não encontrado: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dados inválidos em grades.csv: {e}",
        )

    if dia_semana:
        grades = [g for g in grades if g.dia_semana.lower() == dia_semana.lower()]
    if turno:
        grades = [g for g in grades if g.turno.lower() == turno.lower()]

    return grades


@router.get(
    "/../salas",
    response_model=list[Sala],
    summary="Listar salas",
    description="Retorna a lista de todas as salas.",
)
def listar_salas(
    bloco: str | None = Query(None, description="Filtrar por bloco"),
    status_sala: str | None = Query(None, description="Filtrar por status"),
    provider: AlocacaoProviderInterface = Depends(get_provider),
    token: dict = Depends(auth_handler.decode_token),
) -> list[Sala]:
    """GET /api/salas?bloco=A&status_sala=disponivel

    Protegido por JWT (RNF002).
    """
    try:
        salas = provider.listar_salas()
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Arquivo de salas não encontrado: {e}",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dados inválidos em salas.csv: {e}",
        )

    if bloco:
        salas = [s for s in salas if s.bloco.lower() == bloco.lower()]
    if status_sala:
        salas = [s for s in salas if s.status.lower() == status_sala.lower()]

    return salas


@router.get(
    "/../restricoes",
    response_model=list[Restricao],
    summary="Listar restrições",
    description="Retorna a lista de restrições de alocação.",
)
def listar_restricoes(
    especialidade: str | None = Query(None, description="Filtrar por especialidade"),
    provider: AlocacaoProviderInterface = Depends(get_provider),
    token: dict = Depends(auth_handler.decode_token),
) -> list[Restricao]:
    """GET /api/restricoes?especialidade=pediatria

    Protegido por JWT (RNF002).

    Nota: Atualmente retorna lista vazia. Provider expandido na fase 4
    quando restrições são sincronizadas do AGHU.
    """
    # TODO: Implementar leitura de restrições quando Provider AGHU estiver disponível
    # Por enquanto, retorna lista vazia (compatível com especificação)
    return []

