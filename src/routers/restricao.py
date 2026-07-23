"""Router SAA — Restrições (GET /api/restricoes)"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from src.models.schemas import Restricao
from src.repositories.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.repositories.interfaces.restricao_provider_interface import RestricaoProviderInterface
from src.services.restricao_service import RestricaoService

router = APIRouter(prefix="/api/restricoes", tags=["SAA — Restrições"])

# Mesmo caminho usado pela escrita em POST /api/importacao/restricoes.
_RESTRICOES_PATH = Path(os.getenv("SAA_RESTRICOES_PATH", "data/restricoes.csv"))


def get_restricao_provider() -> RestricaoProviderInterface:
    return RestricaoCsvProvider(caminho=_RESTRICOES_PATH)


def get_restricao_service(
    provider: RestricaoProviderInterface = Depends(get_restricao_provider),
) -> RestricaoService:
    return RestricaoService(provider)


@router.get("", response_model=list[Restricao], summary="Listar restrições")
def listar_restricoes(
    service: RestricaoService = Depends(get_restricao_service),
):
    try:
        return service.listar_restricoes()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
