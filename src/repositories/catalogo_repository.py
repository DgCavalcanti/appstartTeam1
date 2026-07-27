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
from src.models.saa import PavimentoCatalogo, RestricaoPadrao, UnidadeCatalogo

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
        """
        Pavimentos agrupados por andar — pavimento 1 e todos os seus blocos,
        depois pavimento 2 e os seus, e assim por diante. Nunca alfabético:
        ordenar por `bloco` (texto) colocaria "Bloco Anexo" antes de "Bloco D",
        porque 'A' vem antes de 'D' no alfabeto — sem relação nenhuma com a
        disposição física do prédio.

        `id` desempata dentro do mesmo andar, preservando a ordem em que os
        blocos daquele andar foram informados (`dados_referencia.PAVIMENTOS`).
        """
        resultado = await self.sessao.execute(
            select(PavimentoCatalogo).order_by(
                PavimentoCatalogo.andar, PavimentoCatalogo.id
            )
        )
        return list(resultado.scalars())

    #: Campos de sala que o gestor edita no panorama padrão.
    CAMPOS_SALA = ("padrao_1est", "padrao_2est", "esp_1est", "esp_2est", "fechada")

    async def editar_pavimento_padrao(
        self, pavimento_id: int, contagens: dict[str, int]
    ) -> PavimentoCatalogo | None:
        """
        Edita as contagens de salas de um pavimento do catálogo (panorama padrão).

        Só mexe nas contagens — adicionar/remover pavimentos está fora de escopo,
        o prédio é fixo. Vale só para cenários futuros; os já salvos guardam a
        cópia deles.
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

    # -- Regras padrão de restrição (obrigatoriedade/preferência) ----------
    #
    # Vivem no catálogo global, por Unidade_Funcional + pavimento. São a
    # pré-configuração aplicada a cada NOVO cenário (requisito 4): o gestor as
    # edita aqui sem depender de reimportar grades, e editar/remover uma regra
    # daqui não altera cenários já criados — cada cenário guarda sua própria
    # cópia das restrições no momento em que foi criado.

    async def listar_restricoes_padrao(self) -> list[RestricaoPadrao]:
        resultado = await self.sessao.execute(
            select(RestricaoPadrao).order_by(
                RestricaoPadrao.nome_unidade, RestricaoPadrao.pavimento_catalogo_id
            )
        )
        return list(resultado.scalars())

    async def definir_restricao_padrao(
        self, nome_unidade: str, pavimento_catalogo_id: int, tipo: str
    ) -> RestricaoPadrao:
        """
        Cria ou substitui a regra padrão de uma unidade.

        Só pode existir uma obrigatoriedade padrão por unidade — igual à regra
        de cenário: uma unidade fica num pavimento só a semana inteira.
        """
        if tipo not in (OBRIGATORIO, PREFERENCIAL):
            raise ValueError(
                f"tipo inválido: {tipo!r}. Esperado {OBRIGATORIO!r} ou {PREFERENCIAL!r}"
            )
        chave = normalizar(nome_unidade)
        if not chave:
            raise ValueError("nome da unidade não pode ser vazio")

        pavimento = await self.sessao.get(PavimentoCatalogo, pavimento_catalogo_id)
        if pavimento is None:
            raise ValueError(f"pavimento {pavimento_catalogo_id} não existe no catálogo")

        if tipo == OBRIGATORIO:
            existentes = await self.sessao.execute(
                select(RestricaoPadrao).where(
                    RestricaoPadrao.unidade_normalizada == chave,
                    RestricaoPadrao.tipo == OBRIGATORIO,
                )
            )
            for antiga in existentes.scalars():
                await self.sessao.delete(antiga)
            await self.sessao.flush()

        existente = await self.sessao.execute(
            select(RestricaoPadrao).where(
                RestricaoPadrao.unidade_normalizada == chave,
                RestricaoPadrao.pavimento_catalogo_id == pavimento_catalogo_id,
                RestricaoPadrao.tipo == tipo,
            )
        )
        atual = existente.scalar_one_or_none()
        if atual is not None:
            return atual

        regra = RestricaoPadrao(
            nome_unidade=nome_unidade.strip(),
            unidade_normalizada=chave,
            pavimento_catalogo_id=pavimento_catalogo_id,
            tipo=tipo,
        )
        self.sessao.add(regra)
        await self.sessao.flush()
        logger.info(
            "regra padrão: %s → %s — %s (%s)",
            nome_unidade,
            pavimento.bloco,
            pavimento.nome,
            tipo,
        )
        return regra

    async def remover_restricao_padrao(self, restricao_padrao_id: int) -> bool:
        regra = await self.sessao.get(RestricaoPadrao, restricao_padrao_id)
        if regra is None:
            return False
        await self.sessao.delete(regra)
        await self.sessao.flush()
        return True

    async def restricoes_padrao_por_unidade(self) -> dict[str, list[RestricaoPadrao]]:
        """Regras padrão agrupadas por unidade normalizada — usado ao criar um cenário."""
        regras = await self.listar_restricoes_padrao()
        agrupado: dict[str, list[RestricaoPadrao]] = {}
        for regra in regras:
            agrupado.setdefault(regra.unidade_normalizada, []).append(regra)
        return agrupado

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
        for bloco, nome, andar, p1, p2, e1, e2, fec in dados_referencia.PAVIMENTOS:
            self.sessao.add(
                PavimentoCatalogo(
                    bloco=bloco,
                    nome=nome,
                    andar=andar,
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
