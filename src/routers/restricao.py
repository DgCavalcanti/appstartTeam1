"""Router SAA — Restrições (GET /api/restricoes)"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status

from src.controllers.restricao_controller import RestricaoController
from src.models.schemas import Restricao
from src.providers.implementations.restricao_csv_provider import RestricaoCsvProvider
from src.providers.interfaces.restricao_provider_interface import RestricaoProviderInterface

router = APIRouter(prefix="/api/restricoes", tags=["SAA — Restrições"])

# Mesmo caminho usado pela escrita em POST /api/importacao/restricoes.
_RESTRICOES_PATH = Path(os.getenv("SAA_RESTRICOES_PATH", "data/restricoes.csv"))


def get_restricao_provider() -> RestricaoProviderInterface:
    return RestricaoCsvProvider(caminho=_RESTRICOES_PATH)


def get_restricao_controller(
    provider: RestricaoProviderInterface = Depends(get_restricao_provider),
) -> RestricaoController:
    return RestricaoController(provider)


@router.get("", response_model=list[Restricao], summary="Listar restrições")
def listar_restricoes(
    controller: RestricaoController = Depends(get_restricao_controller),
):
    try:
        return controller.listar_restricoes()
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
