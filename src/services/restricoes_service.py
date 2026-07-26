"""
restricoes_service.py — Etapa 4: obrigatoriedades e preferências.

A distinção entre as duas é o que define o caráter do algoritmo:

- **Obrigatória** é uma trava. A clínica vai para aquele pavimento mesmo que
  isso deixe grades sem sala. É a única coisa capaz de gerar sobra.
- **Preferencial** é um puxão. Entra como afinidade e cede quando o pavimento
  não comporta a clínica inteira — um desejo nunca faz ninguém perder
  atendimento havendo espaço ao lado.

Referência: SAA_Arquitetura.pdf, seções 7 e 8.
"""

from __future__ import annotations

import logging
from typing import Iterable, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entidades import OBRIGATORIO, PREFERENCIAL, Clinica
from src.domain.importacao import normalizar
from src.models.saa import Alocacao, Restricao, RestricaoPadrao
from src.services.processo_service import ProcessoService

logger = logging.getLogger(__name__)

ETAPA_RESTRICOES = 4

#: Peso da regra padrão na nota de afinidade — mesmo peso da preferência
#: manual do gestor (seção 13 do documento deixa os pesos em aberto).
PESO_PREFERENCIA_PADRAO = 1.0


# ---------------------------------------------------------------------------
# Regras padrão → pesos do motor (pré-alocação)
# ---------------------------------------------------------------------------
#
# Funções puras, sem sessão: usadas tanto na prévia da importação quanto na
# execução inicial ao criar um cenário, para que a pré-alocação já saia
# ponderada pelas regras padrão do catálogo — em vez de só persistir a
# restrição e deixar o resultado desatualizado até o gestor reexecutar a
# etapa 5 à mão.


def resolver_regras_padrao(
    regras: Iterable[RestricaoPadrao],
    pavimentos_bloco_nome: Sequence[tuple[str, str]],
) -> tuple[tuple[str, int, str], ...]:
    """
    Casa cada regra padrão do catálogo com o índice 1..N do pavimento deste
    cálculo, pela dupla (bloco, nome).

    `pavimentos_bloco_nome` precisa estar na MESMA ordem/índice dos pavimentos
    que vão para o motor (1-based) — é assim que a regra aponta para "o
    3º pavimento desta lista" em vez de um id de catálogo que o cálculo atual
    nem conhece. Regra cujo pavimento não está entre os informados (ex.: painel
    de salas customizado sem aquele pavimento) é ignorada.

    Devolve triplas (unidade_normalizada, pavimento_indice, tipo) — o formato
    comum entre a persistência (`RestricaoPadraoEntrada`) e o motor
    (`pesos_do_motor`).
    """
    indice_por_bloco_nome = {
        par: indice for indice, par in enumerate(pavimentos_bloco_nome, start=1)
    }
    resolvidas = []
    for regra in regras:
        indice = indice_por_bloco_nome.get((regra.pavimento.bloco, regra.pavimento.nome))
        if indice is None:
            continue
        resolvidas.append((regra.unidade_normalizada, indice, regra.tipo))
    return tuple(resolvidas)


def pesos_do_motor(
    regras_resolvidas: Iterable[tuple[str, int, str]],
    clinicas: Iterable[Clinica],
) -> tuple[dict[int, int], dict[tuple[int, int], float]]:
    """
    Traduz regras padrão já resolvidas (unidade_normalizada, pavimento_indice,
    tipo) em `obrigatorias`/`afinidade` — os dois parâmetros que
    `EntradaAlocacao` espera do motor.
    """
    ids_por_unidade = {normalizar(c.nome): c.id for c in clinicas}
    obrigatorias: dict[int, int] = {}
    afinidade: dict[tuple[int, int], float] = {}
    for unidade_normalizada, pavimento_indice, tipo in regras_resolvidas:
        clinica_id = ids_por_unidade.get(unidade_normalizada)
        if clinica_id is None:
            continue
        if tipo == OBRIGATORIO:
            obrigatorias[clinica_id] = pavimento_indice
        elif tipo == PREFERENCIAL:
            chave = (clinica_id, pavimento_indice)
            afinidade[chave] = afinidade.get(chave, 0.0) + PESO_PREFERENCIA_PADRAO
    return obrigatorias, afinidade


class RestricoesService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.processo = ProcessoService(sessao)

    def listar(self, cenario: Alocacao) -> list[dict]:
        unidades = {u.id: u.unidade_nome for u in cenario.unidades}
        pavimentos = {p.id: p.nome_completo for p in cenario.pavimentos}
        return [
            {
                "id": r.id,
                "unidade_id": r.alocacao_unidade_id,
                "unidade": unidades.get(r.alocacao_unidade_id, "?"),
                "pavimento_id": r.pavimento_id,
                "pavimento": pavimentos.get(r.pavimento_id, "?"),
                "tipo": r.tipo,
            }
            for r in cenario.restricoes
        ]

    async def definir(
        self, cenario: Alocacao, unidade_id: int, pavimento_id: int, tipo: str
    ) -> Restricao:
        """
        Cria ou substitui uma restrição.

        Uma unidade só pode ter uma obrigatoriedade: ela fica num pavimento só
        na semana inteira, então duas travas seriam contraditórias. Definir uma
        nova substitui a anterior em vez de acumular um conflito silencioso.
        """
        if tipo not in (OBRIGATORIO, PREFERENCIAL):
            raise ValueError(
                f"tipo inválido: {tipo!r}. Esperado {OBRIGATORIO!r} ou {PREFERENCIAL!r}"
            )
        self._validar_pertence(cenario, unidade_id, pavimento_id)

        if tipo == OBRIGATORIO:
            anteriores = [
                r
                for r in cenario.restricoes
                if r.alocacao_unidade_id == unidade_id and r.tipo == OBRIGATORIO
            ]
            for antiga in anteriores:
                cenario.restricoes.remove(antiga)
                await self.sessao.delete(antiga)

        existente = next(
            (
                r
                for r in cenario.restricoes
                if r.alocacao_unidade_id == unidade_id
                and r.pavimento_id == pavimento_id
                and r.tipo == tipo
            ),
            None,
        )
        if existente is not None:
            return existente

        restricao = Restricao(
            alocacao_id=cenario.id,
            alocacao_unidade_id=unidade_id,
            pavimento_id=pavimento_id,
            tipo=tipo,
        )
        self.sessao.add(restricao)
        cenario.restricoes.append(restricao)

        await self.processo.registrar_alteracao(cenario, ETAPA_RESTRICOES)
        logger.info(
            "cenário %d: unidade %d marcada como %s no pavimento %d",
            cenario.id,
            unidade_id,
            tipo,
            pavimento_id,
        )
        return restricao

    async def remover(self, cenario: Alocacao, restricao_id: int) -> bool:
        restricao = next(
            (r for r in cenario.restricoes if r.id == restricao_id), None
        )
        if restricao is None:
            return False

        cenario.restricoes.remove(restricao)
        await self.sessao.delete(restricao)
        await self.processo.registrar_alteracao(cenario, ETAPA_RESTRICOES)
        return True

    @staticmethod
    def _validar_pertence(
        cenario: Alocacao, unidade_id: int, pavimento_id: int
    ) -> None:
        if not any(u.id == unidade_id for u in cenario.unidades):
            raise ValueError(
                f"unidade {unidade_id} não pertence ao cenário {cenario.id}"
            )
        if not any(p.id == pavimento_id for p in cenario.pavimentos):
            raise ValueError(
                f"pavimento {pavimento_id} não pertence ao cenário {cenario.id}"
            )
