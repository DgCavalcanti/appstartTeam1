"""
catalogo_repository.py — Os catálogos globais.

Sobrevivem entre cenários: guardam a estrutura real do prédio e a lista de
unidades funcionais do ambulatório, e aprendem unidades novas a cada importação.

Os dados de referência (mapa do HC e unidades SIM/NÃO) vivem em
`dados_referencia.py` e são semeados na primeira execução.
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from src.domain.entidades import OBRIGATORIO, PREFERENCIAL
from src.domain.importacao import normalizar
from src.models.saa import (
    PavimentoCatalogo,
    Restricao,
    RestricaoCatalogo,
    UnidadeCatalogo,
)

# Importado pelo módulo, não pelo pacote: `from src.repositories import ...`
# reentraria em __init__.py, que ainda está sendo inicializado.
import src.repositories.dados_referencia as dados_referencia

logger = logging.getLogger(__name__)


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

        Uma unidade nova que o AGHU traga e o catálogo não conheça entra
        participando (`participa_default=True`) e fica visível para o gestor
        revisar na etapa 2 — é a reconciliação do passo 10 do pipeline.
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

    async def participacao_padrao(self, nomes: list[str]) -> dict[str, bool]:
        """
        Para cada nome informado, se ele participa por padrão segundo o catálogo.

        É o que substitui a antiga heurística do sufixo "(AMBULATÓRIO)": a
        resposta vem da lista real de unidades do ambulatório. Unidade que o
        catálogo não conhece entra como participante (será revisada).
        """
        por_chave = {u.nome_normalizado: u.participa_default for u in await self.listar_unidades()}
        return {nome: por_chave.get(normalizar(nome), True) for nome in nomes}

    # -- Pavimentos --------------------------------------------------------

    async def listar_pavimentos(self) -> list[PavimentoCatalogo]:
        resultado = await self.sessao.execute(
            select(PavimentoCatalogo).order_by(
                PavimentoCatalogo.bloco, PavimentoCatalogo.id
            )
        )
        return list(resultado.scalars())

    #: Campos de sala que o gestor edita no panorama padrão.
    CAMPOS_SALA = ("padrao_1est", "padrao_2est", "esp_1est", "esp_2est", "fechada")

    async def editar_pavimento_padrao(
        self, pavimento_id: int, contagens: dict[str, int]
    ) -> PavimentoCatalogo | None:
        """
        Edita as contagens de salas de um pavimento do catálogo (padrão global).

        Só mexe nas contagens — adicionar ou remover pavimentos está fora de
        escopo, o prédio é fixo. Vale só para cenários futuros.
        """
        pavimento = await self.sessao.get(PavimentoCatalogo, pavimento_id)
        if pavimento is None:
            return None

        desconhecidos = set(contagens) - set(self.CAMPOS_SALA)
        if desconhecidos:
            raise ValueError(
                f"campos desconhecidos: {sorted(desconhecidos)}. "
                f"Esperado: {list(self.CAMPOS_SALA)}"
            )
        for campo, valor in contagens.items():
            quantidade = int(valor)
            if quantidade < 0:
                raise ValueError(f"{campo} não pode ser negativo")
            setattr(pavimento, campo, quantidade)

        await self.sessao.flush()
        return pavimento

    # -- Restrições padrão -------------------------------------------------

    async def listar_restricoes_padrao(self) -> list[RestricaoCatalogo]:
        resultado = await self.sessao.execute(
            select(RestricaoCatalogo).order_by(RestricaoCatalogo.unidade_nome)
        )
        return list(resultado.scalars())

    async def definir_restricao_padrao(
        self, unidade_nome: str, pavimento_catalogo_id: int, tipo: str
    ) -> RestricaoCatalogo:
        """
        Cria ou substitui uma restrição padrão.

        Uma clínica só pode ter uma obrigatoriedade padrão (ela fica num
        pavimento só na semana). Definir uma nova substitui a anterior.
        """
        if tipo not in (OBRIGATORIO, PREFERENCIAL):
            raise ValueError(
                f"tipo inválido: {tipo!r}. Esperado {OBRIGATORIO!r} ou {PREFERENCIAL!r}"
            )
        pavimento = await self.sessao.get(PavimentoCatalogo, pavimento_catalogo_id)
        if pavimento is None:
            raise ValueError(f"pavimento {pavimento_catalogo_id} não existe no catálogo")

        chave = normalizar(unidade_nome)

        if tipo == OBRIGATORIO:
            for antiga in await self.listar_restricoes_padrao():
                if antiga.unidade_normalizada == chave and antiga.tipo == OBRIGATORIO:
                    await self.sessao.delete(antiga)

        existente = await self.sessao.execute(
            select(RestricaoCatalogo).where(
                RestricaoCatalogo.unidade_normalizada == chave,
                RestricaoCatalogo.pavimento_catalogo_id == pavimento_catalogo_id,
                RestricaoCatalogo.tipo == tipo,
            )
        )
        atual = existente.scalar_one_or_none()
        if atual is not None:
            return atual

        restricao = RestricaoCatalogo(
            unidade_nome=unidade_nome.strip(),
            unidade_normalizada=chave,
            pavimento_catalogo_id=pavimento_catalogo_id,
            tipo=tipo,
        )
        self.sessao.add(restricao)
        await self.sessao.flush()
        logger.info(
            "restrição padrão: %s %s no pavimento %d",
            unidade_nome,
            tipo,
            pavimento_catalogo_id,
        )
        return restricao

    async def remover_restricao_padrao(self, restricao_id: int) -> bool:
        restricao = await self.sessao.get(RestricaoCatalogo, restricao_id)
        if restricao is None:
            return False
        await self.sessao.delete(restricao)
        await self.sessao.flush()
        return True

    async def semear_restricoes_no_cenario(self, cenario) -> int:
        """
        Copia as restrições padrão para um cenário recém-criado.

        Casa cada padrão com a cópia do cenário: a clínica pela forma
        normalizada do nome (só as que participam) e o pavimento pelo bloco/nome.
        Padrões sem alvo — clínica ausente/não participante ou pavimento
        removido — são pulados.
        """
        padroes = await self.listar_restricoes_padrao()
        if not padroes:
            return 0

        unidades = {
            normalizar(u.unidade_nome): u for u in cenario.unidades if u.participa
        }
        pavimentos = {(p.bloco, p.nome): p for p in cenario.pavimentos}

        criadas = 0
        for padrao in padroes:
            unidade = unidades.get(padrao.unidade_normalizada)
            pavimento = pavimentos.get((padrao.pavimento.bloco, padrao.pavimento.nome))
            if unidade is None or pavimento is None:
                continue
            restricao = Restricao(
                alocacao_id=cenario.id,
                alocacao_unidade_id=unidade.id,
                pavimento_id=pavimento.id,
                tipo=padrao.tipo,
            )
            self.sessao.add(restricao)
            cenario.restricoes.append(restricao)
            criadas += 1

        if criadas:
            await self.sessao.flush()
            logger.info("cenário %d herdou %d restrições padrão", cenario.id, criadas)
        return criadas

    # -- Semeadura da referência -------------------------------------------

    async def semear_referencia(self) -> dict[str, int]:
        """
        Popula o catálogo com o mapa do HC e as unidades do ambulatório.

        Semeia cada tabela apenas quando vazia, para não sobrescrever o que o
        gestor tenha ajustado. Num banco já semeado com dados antigos, apague o
        arquivo do SQLite para forçar a resemeadura com os dados de referência.
        """
        return {
            "pavimentos": await self._semear_pavimentos(),
            "unidades": await self._semear_unidades(),
        }

    async def _semear_pavimentos(self) -> int:
        if await self.listar_pavimentos():
            return 0
        for bloco, nome, p1, p2, e1, e2, fec in dados_referencia.PAVIMENTOS:
            self.sessao.add(
                PavimentoCatalogo(
                    bloco=bloco,
                    nome=nome,
                    padrao_1est=p1,
                    padrao_2est=p2,
                    esp_1est=e1,
                    esp_2est=e2,
                    fechada=fec,
                )
            )
        await self.sessao.flush()
        logger.info(
            "catálogo de pavimentos semeado: %d pavimentos, %d estações",
            len(dados_referencia.PAVIMENTOS),
            dados_referencia.capacidade_total(),
        )
        return len(dados_referencia.PAVIMENTOS)

    async def _semear_unidades(self) -> int:
        if await self.listar_unidades():
            return 0
        for nome, participa in dados_referencia.UNIDADES:
            self.sessao.add(
                UnidadeCatalogo(
                    nome=nome,
                    nome_normalizado=normalizar(nome),
                    participa_default=participa,
                )
            )
        await self.sessao.flush()
        logger.info(
            "catálogo de unidades semeado: %d unidades, %d participam",
            len(dados_referencia.UNIDADES),
            dados_referencia.total_participantes(),
        )
        return len(dados_referencia.UNIDADES)
