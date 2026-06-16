"""Router SAA — Salas (GET /api/salas, GET /api/salas/{sala_id})"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.controllers.sala_controller import SalaController
from src.models.schemas import Sala
from src.providers.implementations.sala_csv_provider import SalaCsvProvider
from src.providers.interfaces.sala_provider_interface import SalaProviderInterface

router = APIRouter(prefix="/api/salas", tags=["SAA — Salas"])

# Caminho único usado tanto para leitura (este router) quanto para gravação
# (POST /api/importacao/salas, em importacao.py) — garante que um upload
# sempre afete o mesmo arquivo que esta tela lê.
_SALAS_PATH = Path(os.getenv("SAA_SALAS_PATH", "data/salas.csv"))


def get_sala_provider() -> SalaProviderInterface:
    return SalaCsvProvider(caminho=_SALAS_PATH)


def get_sala_controller(
    provider: SalaProviderInterface = Depends(get_sala_provider),
) -> SalaController:
    return SalaController(provider)


@router.get("", response_model=list[Sala], summary="Listar salas")
def listar_salas(
    bloco: str | None = Query(None),
    status_sala: str | None = Query(None, alias="status"),
    especialidade: str | None = Query(None),
    controller: SalaController = Depends(get_sala_controller),
):
    try:
        return controller.listar_salas(bloco=bloco, status=status_sala, especialidade=especialidade)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))


@router.get("/{sala_id}", response_model=Sala, summary="Buscar sala por ID")
def buscar_sala(
    sala_id: str,
    controller: SalaController = Depends(get_sala_controller),
):
    try:
        sala = controller.buscar_sala(sala_id)
    except (FileNotFoundError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    if sala is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sala '{sala_id}' não encontrada.")
    return sala
