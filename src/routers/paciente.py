from fastapi import APIRouter, Depends
from typing import List

from ..dependencies import get_paciente_provider
from ..repositories.interfaces.paciente_provider_interface import PacienteProviderInterface
from ..services.paciente_service import PacienteService
from ..auth.auth import auth_handler

# --- PONTO ÚNICO DE CONFIGURAÇÃO PARA ESTE ROTEADOR ---
# Para usar o banco de dados em produção, altere esta linha para "postgres"
STRATEGY = "csv"
# ----------------------------------------------------

router = APIRouter(
    prefix="/api/pacientes",
    tags=["Pacientes"],
    dependencies=[Depends(auth_handler.decode_token)]
)

def get_paciente_service(
    provider: PacienteProviderInterface = Depends(get_paciente_provider(STRATEGY)),
) -> PacienteService:
    return PacienteService(provider)

@router.get("", response_model=List[dict])
async def listar_pacientes(
    service: PacienteService = Depends(get_paciente_service),
):
    """Lista todos os pacientes da fonte de dados configurada no roteador."""
    return await service.listar_pacientes()

@router.get("/{codigo}", response_model=dict)
async def obter_paciente(
    codigo: int,
    service: PacienteService = Depends(get_paciente_service),
):
    """Obtém um paciente pelo código a partir da fonte de dados configurada no roteador."""
    return await service.obter_paciente_por_codigo(codigo)
