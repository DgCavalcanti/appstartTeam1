"""
catalogo_repository.py — Os catálogos globais.

Sobrevivem entre cenários: aprendem unidades novas a cada importação e guardam
a estrutura do prédio para pré-preencher a próxima alocação.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from src.domain.importacao import normalizar
from src.models.saa import PavimentoCatalogo, UnidadeCatalogo

logger = logging.getLogger(__name__)


#: Estrutura do HC usada na primeira execução, quando o catálogo está vazio.
#: 9 pavimentos, 231 estações por turno — a ordem de grandeza do prédio real.
PAVIMENTOS_SEMENTE: tuple[dict, ...] = (
    {"bloco": "Bloco A", "nome": "Térreo",    "padrao_1est": 8,  "padrao_2est": 9,  "esp_1est": 4, "esp_2est": 2},
    {"bloco": "Bloco A", "nome": "1º andar",  "padrao_1est": 7,  "padrao_2est": 7,  "esp_1est": 2, "esp_2est": 2},
    {"bloco": "Bloco A", "nome": "2º andar",  "padrao_1est": 6,  "padrao_2est": 7,  "esp_1est": 2, "esp_2est": 2},
    {"bloco": "Bloco B", "nome": "Térreo",    "padrao_1est": 9,  "padrao_2est": 8,  "esp_1est": 2, "esp_2est": 2},
    {"bloco": "Bloco B", "nome": "1º andar",  "padrao_1est": 6,  "padrao_2est": 6,  "esp_1est": 2, "esp_2est": 1},
    {"bloco": "Bloco B", "nome": "2º andar",  "padrao_1est": 7,  "padrao_2est": 7,  "esp_1est": 2, "esp_2est": 1},
    {"bloco": "Bloco C", "nome": "Térreo",    "padrao_1est": 6,  "padrao_2est": 5,  "esp_1est": 2, "esp_2est": 1},
    {"bloco": "Bloco C", "nome": "1º andar",  "padrao_1est": 7,  "padrao_2est": 7,  "esp_1est": 4, "esp_2est": 1},
    {"bloco": "Bloco C", "nome": "2º andar",  "padrao_1est": 5,  "padrao_2est": 5,  "esp_1est": 2, "esp_2est": 1},
)


class CatalogoRepository:
    def __init__(self, sessao) -> None:
        self.sessao = sessao

    # -- Unidades ----------------------------------------------------------

    async def listar_unidades(self) -> list[UnidadeCatalogo]:
        resultado = await self.sessao.execute(
            select(UnidadeCatalogo).order_by(UnidadeCatalogo.nome)
        )
        return list(resultado.scalars())

    async def aprender_unidades(self, nomes: list[str]) -> int:
        """
        Registra unidades ainda desconhecidas. Devolve quantas foram criadas.

        Novas entram com `participa_default=True`: o gestor decide na etapa 2
        quem não ocupa consultório.
        """
        existentes = {u.nome_normalizado for u in await self.listar_unidades()}
        criadas = 0
        for nome in nomes:
            chave = normalizar(nome)
            if not chave or chave in existentes:
                continue
            self.sessao.add(
                UnidadeCatalogo(
                    nome=nome.strip(),
                    nome_normalizado=chave,
                    participa_default=True,
                )
            )
            existentes.add(chave)
            criadas += 1
        if criadas:
            await self.sessao.flush()
            logger.info("catálogo aprendeu %d unidades novas", criadas)
        return criadas

    async def definir_participacao(self, nome: str, participa: bool) -> bool:
        """Marca uma unidade como participante ou não. False se ela não existe."""
        chave = normalizar(nome)
        resultado = await self.sessao.execute(
            select(UnidadeCatalogo).where(UnidadeCatalogo.nome_normalizado == chave)
        )
        unidade = resultado.scalar_one_or_none()
        if unidade is None:
            return False
        unidade.participa_default = participa
        await self.sessao.flush()
        return True

    async def unidades_excluidas(self) -> frozenset[str]:
        """Nomes normalizados das unidades que não participam — entrada do passo 2."""
        return frozenset(
            u.nome_normalizado
            for u in await self.listar_unidades()
            if not u.participa_default
        )

    # -- Pavimentos --------------------------------------------------------

    async def listar_pavimentos(self) -> list[PavimentoCatalogo]:
        resultado = await self.sessao.execute(
            select(PavimentoCatalogo).order_by(
                PavimentoCatalogo.bloco, PavimentoCatalogo.nome
            )
        )
        return list(resultado.scalars())

    async def semear_pavimentos(self) -> int:
        """
        Popula a estrutura do prédio na primeira execução.

        Não sobrescreve nada: se o catálogo já tem pavimentos, não faz nada.
        """
        if await self.listar_pavimentos():
            return 0
        for entrada in PAVIMENTOS_SEMENTE:
            self.sessao.add(PavimentoCatalogo(**entrada))
        await self.sessao.flush()
        logger.info("catálogo de pavimentos semeado com %d entradas", len(PAVIMENTOS_SEMENTE))
        return len(PAVIMENTOS_SEMENTE)
