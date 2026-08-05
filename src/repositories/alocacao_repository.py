"""
alocacao_repository.py — Persistência do cenário de alocação.

Traduz o que o domínio produziu (slots, demandas, resultado do motor) nas
tabelas do cenário, e de volta. Cada alocação guarda sua própria cópia dos
insumos: reabrir um cenário antigo mostra exatamente o que gerou aquele
resultado.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.alocacao import ResultadoAlocacao
from src.domain.entidades import Clinica, capacidade_em_estacoes
from src.domain.importacao import GradeDemanda as GradeDemandaDominio
from src.domain.importacao import GradeSlot as GradeSlotDominio
from src.domain.importacao import normalizar
from src.domain.processo import ETAPAS, PENDENTE, PREENCHIDA, RASCUNHO
from src.models.saa import (
    Alocacao,
    AlocacaoEtapa,
    AlocacaoResultado,
    AlocacaoUnidade,
    GradeDemanda,
    GradeSlot,
    Pavimento,
    Restricao,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PavimentoEntrada:
    """
    Um pavimento como o gestor o edita na etapa 3: contagens de salas por tipo.

    A capacidade não vem daqui — é derivada, para não divergir das contagens.
    """

    bloco: str
    nome: str
    #: Número do andar — usado só para agrupar a listagem (nunca alfabética).
    andar: int = 0
    padrao_1est: int = 0
    padrao_2est: int = 0
    esp_1est: int = 0
    esp_2est: int = 0
    fechada: int = 0

    @property
    def capacidade(self) -> int:
        return capacidade_em_estacoes(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )

    @property
    def capacidade_padrao(self) -> int:
        """Estações só das salas PADRÃO — o pool "padrao" que o motor usa."""
        return capacidade_em_estacoes(
            padrao_1est=self.padrao_1est,
            padrao_2est=self.padrao_2est,
        )

    @property
    def capacidade_especializada(self) -> int:
        """Estações só das salas ESPECIALIZADAS — o pool reservado do motor."""
        return capacidade_em_estacoes(
            esp_1est=self.esp_1est,
            esp_2est=self.esp_2est,
        )

    @property
    def nome_completo(self) -> str:
        return f"{self.bloco} — {self.nome}"


@dataclass(frozen=True)
class RestricaoPadraoEntrada:
    """
    Uma regra padrão já resolvida contra os índices do cenário sendo criado.

    `unidade_normalizada` casa com `AlocacaoUnidade.unidade_nome` pela forma
    normalizada; `pavimento_indice` é o índice 1..N atribuído a `pavimentos`
    em `criar()` — o mesmo esquema que `PavimentoEntrada` já usa.
    """

    unidade_normalizada: str
    pavimento_indice: int
    tipo: str


class AlocacaoRepository:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    # -- Leitura -----------------------------------------------------------

    async def listar(self) -> list[Alocacao]:
        """Cenários do mais recente para o mais antigo — a base do histórico."""
        resultado = await self.sessao.execute(
            select(Alocacao).order_by(Alocacao.criado_em.desc(), Alocacao.id.desc())
        )
        return list(resultado.scalars())

    async def obter(self, alocacao_id: int) -> Alocacao | None:
        """
        Carrega um cenário com seus insumos.

        Usa `select` em vez de `session.get` de propósito: o `get` devolve o
        objeto do cache de identidade sem executar consulta, e as coleções de um
        cenário recém-criado ficariam sem carregar — o que estoura em contexto
        assíncrono, onde não existe lazy load.
        """
        resultado = await self.sessao.execute(
            select(Alocacao).where(Alocacao.id == alocacao_id)
        )
        return resultado.scalar_one_or_none()

    async def contar(self) -> int:
        resultado = await self.sessao.execute(select(func.count()).select_from(Alocacao))
        return int(resultado.scalar_one())

    # -- Escrita -----------------------------------------------------------

    async def criar(
        self,
        *,
        nome: str,
        clinicas: tuple[Clinica, ...],
        slots: tuple[GradeSlotDominio, ...],
        demandas: tuple[GradeDemandaDominio, ...],
        pavimentos: tuple[PavimentoEntrada, ...],
        resultado: ResultadoAlocacao | None = None,
        unidades_excluidas: tuple[str, ...] = (),
        origem_id: int | None = None,
        restricoes_padrao: tuple[RestricaoPadraoEntrada, ...] = (),
    ) -> Alocacao:
        """
        Grava um cenário completo e autocontido.

        `clinicas` traz os ids que o resultado do motor referencia; as unidades
        excluídas entram com `participa=False`, preservando no cenário a decisão
        de quem ficou de fora.
        """
        cenario = Alocacao(
            nome=nome,
            status=RASCUNHO,
            etapa_atual=1,
            origem_id=origem_id,
        )
        self.sessao.add(cenario)
        await self.sessao.flush()

        self._semear_etapas(cenario, resultado is not None)

        # Pavimentos — a cópia própria do cenário.
        pavimentos_orm: dict[int, Pavimento] = {}
        for indice, entrada in enumerate(pavimentos, start=1):
            registro = Pavimento(
                alocacao_id=cenario.id,
                bloco=entrada.bloco,
                nome=entrada.nome,
                andar=entrada.andar,
                padrao_1est=entrada.padrao_1est,
                padrao_2est=entrada.padrao_2est,
                esp_1est=entrada.esp_1est,
                esp_2est=entrada.esp_2est,
                fechada=entrada.fechada,
            )
            self.sessao.add(registro)
            # O motor referencia os pavimentos pelo índice 1..N que o router
            # atribuiu; guardamos o mapa para traduzir o resultado depois.
            pavimentos_orm[indice] = registro
        await self.sessao.flush()

        # Unidades participantes.
        unidades_orm: dict[str, AlocacaoUnidade] = {}
        for clinica in clinicas:
            unidade = AlocacaoUnidade(
                alocacao_id=cenario.id,
                unidade_nome=clinica.nome,
                participa=True,
            )
            self.sessao.add(unidade)
            unidades_orm[clinica.nome] = unidade

        # Unidades que o gestor tirou da conta ficam registradas no cenário.
        for nome_excluido in unidades_excluidas:
            if nome_excluido in unidades_orm:
                continue
            unidade = AlocacaoUnidade(
                alocacao_id=cenario.id,
                unidade_nome=nome_excluido,
                participa=False,
            )
            self.sessao.add(unidade)
            unidades_orm[nome_excluido] = unidade

        await self.sessao.flush()

        # Pré-configuração — regras padrão do catálogo aplicadas a este cenário
        # novo. É só o ponto de partida: o gestor edita/remove livremente na
        # etapa 4 sem tocar no padrão global (RestricaoPadrao).
        if restricoes_padrao:
            unidades_por_chave = {
                normalizar(nome): unidade for nome, unidade in unidades_orm.items()
            }
            for regra in restricoes_padrao:
                unidade = unidades_por_chave.get(regra.unidade_normalizada)
                pavimento = pavimentos_orm.get(regra.pavimento_indice)
                if unidade is None or pavimento is None:
                    continue
                self.sessao.add(
                    Restricao(
                        alocacao_id=cenario.id,
                        alocacao_unidade_id=unidade.id,
                        pavimento_id=pavimento.id,
                        tipo=regra.tipo,
                    )
                )
            await self.sessao.flush()

        # Camada de origem: os slots.
        for slot in slots:
            unidade = unidades_orm.get(slot.unidade)
            if unidade is None:
                continue
            self.sessao.add(
                GradeSlot(
                    alocacao_unidade_id=unidade.id,
                    profissional=slot.profissional,
                    dia_semana=slot.dia,
                    turno=slot.periodo,
                    revisar=slot.revisar,
                    especialidade=slot.especialidade,
                )
            )

        # Camada derivada: as contagens.
        for demanda in demandas:
            unidade = unidades_orm.get(demanda.unidade)
            if unidade is None:
                continue
            self.sessao.add(
                GradeDemanda(
                    alocacao_unidade_id=unidade.id,
                    dia_semana=demanda.dia,
                    turno=demanda.periodo,
                    quantidade=demanda.quantidade,
                )
            )

        if resultado is not None:
            self._gravar_resultado(resultado, clinicas, unidades_orm, pavimentos_orm)

        await self.sessao.flush()
        logger.info(
            "cenário %d gravado: %d unidades, %d slots, %d pavimentos",
            cenario.id,
            len(unidades_orm),
            len(slots),
            len(pavimentos),
        )
        return cenario

    async def clonar(self, alocacao_id: int, novo_nome: str) -> Alocacao | None:
        """
        Duplica um cenário para criar uma variação.

        Copia todos os insumos e o resultado; o clone aponta para a origem via
        `origem_id`, de modo que o histórico registre de onde ele veio.
        """
        origem = await self.obter(alocacao_id)
        if origem is None:
            return None

        clone = Alocacao(
            nome=novo_nome,
            status=origem.status,
            etapa_atual=origem.etapa_atual,
            origem_id=origem.id,
        )
        self.sessao.add(clone)
        await self.sessao.flush()

        for etapa in origem.etapas:
            self.sessao.add(
                AlocacaoEtapa(
                    alocacao_id=clone.id, numero=etapa.numero, status=etapa.status
                )
            )

        mapa_pavimentos: dict[int, Pavimento] = {}
        for pavimento in origem.pavimentos:
            copia = Pavimento(
                alocacao_id=clone.id,
                bloco=pavimento.bloco,
                nome=pavimento.nome,
                andar=pavimento.andar,
                padrao_1est=pavimento.padrao_1est,
                padrao_2est=pavimento.padrao_2est,
                esp_1est=pavimento.esp_1est,
                esp_2est=pavimento.esp_2est,
                fechada=pavimento.fechada,
            )
            self.sessao.add(copia)
            mapa_pavimentos[pavimento.id] = copia
        await self.sessao.flush()

        mapa_unidades: dict[int, AlocacaoUnidade] = {}
        for unidade in origem.unidades:
            destino = mapa_pavimentos.get(unidade.pavimento_alocado_id or -1)
            copia_unidade = AlocacaoUnidade(
                alocacao_id=clone.id,
                unidade_nome=unidade.unidade_nome,
                participa=unidade.participa,
                pavimento_alocado_id=destino.id if destino else None,
            )
            self.sessao.add(copia_unidade)
            await self.sessao.flush()
            mapa_unidades[unidade.id] = copia_unidade

            for slot in unidade.slots:
                self.sessao.add(
                    GradeSlot(
                        alocacao_unidade_id=copia_unidade.id,
                        profissional=slot.profissional,
                        dia_semana=slot.dia_semana,
                        turno=slot.turno,
                        revisar=slot.revisar,
                        especialidade=slot.especialidade,
                    )
                )
            for demanda in unidade.demandas:
                self.sessao.add(
                    GradeDemanda(
                        alocacao_unidade_id=copia_unidade.id,
                        dia_semana=demanda.dia_semana,
                        turno=demanda.turno,
                        quantidade=demanda.quantidade,
                    )
                )
            for item in unidade.resultados:
                self.sessao.add(
                    AlocacaoResultado(
                        alocacao_unidade_id=copia_unidade.id,
                        dia_semana=item.dia_semana,
                        turno=item.turno,
                        qtd_alocada=item.qtd_alocada,
                        qtd_nao_alocada=item.qtd_nao_alocada,
                    )
                )

        # Restrições — obrigatoriedade/preferência também fazem parte da cópia:
        # sem isso, o clone perderia as travas e afinidades da origem.
        for restricao in origem.restricoes:
            unidade_destino = mapa_unidades.get(restricao.alocacao_unidade_id)
            pavimento_destino = mapa_pavimentos.get(restricao.pavimento_id)
            if unidade_destino is None or pavimento_destino is None:
                continue
            self.sessao.add(
                Restricao(
                    alocacao_id=clone.id,
                    alocacao_unidade_id=unidade_destino.id,
                    pavimento_id=pavimento_destino.id,
                    tipo=restricao.tipo,
                )
            )

        await self.sessao.flush()
        logger.info("cenário %d clonado em %d", origem.id, clone.id)
        return clone

    async def excluir(self, alocacao_id: int) -> bool:
        cenario = await self.obter(alocacao_id)
        if cenario is None:
            return False
        await self.sessao.delete(cenario)
        await self.sessao.flush()
        return True

    async def renomear(self, alocacao_id: int, nome: str) -> bool:
        cenario = await self.obter(alocacao_id)
        if cenario is None:
            return False
        cenario.nome = nome
        await self.sessao.flush()
        return True

    # -- Auxiliares --------------------------------------------------------

    def _semear_etapas(self, cenario: Alocacao, com_resultado: bool) -> None:
        """
        Cria as 6 etapas do cenário.

        A importação (1) já aconteceu; se o motor rodou, a execução (5) também.
        """
        preenchidas = {1}
        if com_resultado:
            preenchidas |= {5}
        for etapa in ETAPAS:
            self.sessao.add(
                AlocacaoEtapa(
                    alocacao_id=cenario.id,
                    numero=etapa.numero,
                    status=PREENCHIDA if etapa.numero in preenchidas else PENDENTE,
                )
            )

    def _gravar_resultado(
        self,
        resultado: ResultadoAlocacao,
        clinicas: tuple[Clinica, ...],
        unidades_orm: dict[str, AlocacaoUnidade],
        pavimentos_orm: dict[int, Pavimento],
    ) -> None:
        from src.domain.entidades import TURNOS

        nomes_por_id = {c.id: c.nome for c in clinicas}

        for item in resultado.por_clinica:
            nome = nomes_por_id.get(item.clinica_id)
            unidade = unidades_orm.get(nome) if nome else None
            if unidade is None:
                continue

            pavimento = pavimentos_orm.get(item.pavimento_id)
            if pavimento is not None:
                unidade.pavimento_alocado_id = pavimento.id

            for indice, (dia, periodo) in enumerate(TURNOS):
                alocada = item.alocado[indice]
                nao_alocada = item.nao_alocado[indice]
                if alocada == 0 and nao_alocada == 0:
                    continue
                self.sessao.add(
                    AlocacaoResultado(
                        alocacao_unidade_id=unidade.id,
                        dia_semana=dia,
                        turno=periodo,
                        qtd_alocada=alocada,
                        qtd_nao_alocada=nao_alocada,
                    )
                )
