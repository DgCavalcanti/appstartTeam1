"""
padroes.py — Padrões globais que os cenários novos herdam.

Duas configurações de referência, editáveis fora do fluxo de um cenário:

- **Panorama de salas**: as contagens de salas por pavimento do catálogo (o mapa
  do HC). Todo cenário novo já nasce com elas.
- **Restrições padrão**: obrigatoriedades e preferências (clínica → pavimento)
  que os cenários novos herdam ao serem criados.

Editar um padrão vale só para cenários futuros; os já salvos ficam intactos,
com a cópia que os gerou.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories import CatalogoRepository
from src.resources.database import get_app_db_session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/padroes", tags=["Padrões"])


# ---------------------------------------------------------------------------
# Panorama de salas (padrão)
# ---------------------------------------------------------------------------


class EdicaoPavimentoPadrao(BaseModel):
    pavimento_id: int
    contagens: dict[str, int]


def _pavimento_dict(p) -> dict:
    return {
        "id": p.id,
        "bloco": p.bloco,
        "nome": p.nome,
        "nome_completo": p.nome_completo,
        "padrao_1est": p.padrao_1est,
        "padrao_2est": p.padrao_2est,
        "esp_1est": p.esp_1est,
        "esp_2est": p.esp_2est,
        "fechada": p.fechada,
        "capacidade": p.capacidade,
    }


@router.get("/panorama", summary="Panorama de salas padrão")
async def ler_panorama_padrao(sessao: AsyncSession = Depends(get_app_db_session)):
    catalogo = CatalogoRepository(sessao)
    if any((await catalogo.semear_referencia()).values()):
        await sessao.commit()
    pavimentos = await catalogo.listar_pavimentos()
    return {
        "pavimentos": [_pavimento_dict(p) for p in pavimentos],
        "capacidade_total": sum(p.capacidade for p in pavimentos),
    }


@router.put("/panorama", summary="Editar o panorama de salas padrão em lote")
async def editar_panorama_padrao(
    edicoes: list[EdicaoPavimentoPadrao],
    sessao: AsyncSession = Depends(get_app_db_session),
):
    catalogo = CatalogoRepository(sessao)
    try:
        for edicao in edicoes:
            alterado = await catalogo.editar_pavimento_padrao(
                edicao.pavimento_id, edicao.contagens
            )
            if alterado is None:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    f"pavimento {edicao.pavimento_id} não existe no catálogo",
                )
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    pavimentos = await catalogo.listar_pavimentos()
    return {
        "pavimentos": [_pavimento_dict(p) for p in pavimentos],
        "capacidade_total": sum(p.capacidade for p in pavimentos),
    }


# ---------------------------------------------------------------------------
# Restrições padrão
# ---------------------------------------------------------------------------


class NovaRestricaoPadrao(BaseModel):
    unidade_nome: str
    pavimento_catalogo_id: int
    tipo: str


@router.get("/restricoes", summary="Restrições padrão e opções para defini-las")
async def ler_restricoes_padrao(sessao: AsyncSession = Depends(get_app_db_session)):
    catalogo = CatalogoRepository(sessao)
    if any((await catalogo.semear_referencia()).values()):
        await sessao.commit()

    restricoes = await catalogo.listar_restricoes_padrao()
    unidades = await catalogo.listar_unidades()
    # Só pavimentos com capacidade servem de destino de restrição.
    pavimentos = [p for p in await catalogo.listar_pavimentos() if p.capacidade > 0]

    return {
        "restricoes": [
            {
                "id": r.id,
                "unidade": r.unidade_nome,
                "pavimento_id": r.pavimento_catalogo_id,
                "pavimento": r.pavimento.nome_completo,
                "tipo": r.tipo,
            }
            for r in restricoes
        ],
        # As 62 unidades do catálogo — o gestor pode restringir qualquer uma; só
        # as participantes de um cenário é que herdam a restrição na prática.
        "unidades": [
            {"nome": u.nome, "participa_default": u.participa_default}
            for u in unidades
        ],
        "pavimentos": [
            {"id": p.id, "nome_completo": p.nome_completo} for p in pavimentos
        ],
    }


@router.post(
    "/restricoes",
    status_code=status.HTTP_201_CREATED,
    summary="Definir uma restrição padrão",
)
async def definir_restricao_padrao(
    nova: NovaRestricaoPadrao,
    sessao: AsyncSession = Depends(get_app_db_session),
):
    catalogo = CatalogoRepository(sessao)
    try:
        await catalogo.definir_restricao_padrao(
            nova.unidade_nome, nova.pavimento_catalogo_id, nova.tipo
        )
    except ValueError as erro:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(erro))

    await sessao.commit()
    return await ler_restricoes_padrao(sessao)


@router.delete("/restricoes/{restricao_id}", summary="Remover uma restrição padrão")
async def remover_restricao_padrao(
    restricao_id: int, sessao: AsyncSession = Depends(get_app_db_session)
):
    catalogo = CatalogoRepository(sessao)
    if not await catalogo.remover_restricao_padrao(restricao_id):
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"restrição padrão {restricao_id} não encontrada"
        )
    await sessao.commit()
    return await ler_restricoes_padrao(sessao)
