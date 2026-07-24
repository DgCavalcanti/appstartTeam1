"""
alocacao_service.py — Etapas 5 e 6: executar o motor e ajustar à mão.

Este é o serviço que fecha o ciclo: lê os insumos que o cenário guardou, monta a
entrada do motor, grava o resultado e move a máquina de estados.

Diferente da importação, aqui nada vem de arquivo — tudo sai do banco. É o que
permite reexecutar a alocação depois de o gestor editar grades, salas ou
restrições, sem reimportar a planilha.

Referência: SAA_Arquitetura.pdf, seções 7 e 8.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.alocacao import EntradaAlocacao, ResultadoAlocacao, SolverHeuristico
from src.domain.entidades import (
    NUM_TURNOS,
    OBRIGATORIO,
    PREFERENCIAL,
    TURNOS,
    Clinica,
    Pavimento as PavimentoDominio,
    indice_turno,
)
from src.models.saa import Alocacao, AlocacaoResultado, AlocacaoUnidade
from src.services.processo_service import ETAPA_AJUSTES, ETAPA_EXECUCAO, ProcessoService

logger = logging.getLogger(__name__)


#: Peso da preferência manual do gestor na nota de afinidade.
#:
#: O documento define afinidade como "preferência manual + histórico", mas deixa
#: os pesos em aberto (seção 13). Enquanto isso não é decidido, só a preferência
#: manual pesa — o que já satisfaz a regra de que preferência atrai sem forçar.
PESO_PREFERENCIA_MANUAL = 1.0


class AlocacaoService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao
        self.processo = ProcessoService(sessao)

    # -- Etapa 5 -----------------------------------------------------------

    async def executar(self, cenario: Alocacao) -> ResultadoAlocacao:
        """
        Roda o motor sobre os insumos do cenário e grava o resultado.

        Só as unidades marcadas como participantes entram. Um cenário sem
        unidades participantes ou sem pavimentos é erro de uso, não resultado
        vazio — avisar é melhor que devolver uma alocação que não quer dizer
        nada.
        """
        participantes = [u for u in cenario.unidades if u.participa]
        if not participantes:
            raise ValueError("nenhuma unidade participante: não há o que alocar")
        if not cenario.pavimentos:
            raise ValueError("o cenário não tem pavimentos cadastrados")

        entrada = self._montar_entrada(cenario, participantes)
        resultado = SolverHeuristico().resolver(entrada)

        await self._gravar(cenario, resultado)
        await self.processo.registrar_alteracao(cenario, ETAPA_EXECUCAO)

        logger.info(
            "cenário %d alocado: %d grades alocadas, %d sem sala",
            cenario.id,
            resultado.total_alocado,
            resultado.total_nao_alocado,
        )
        return resultado

    def _montar_entrada(
        self, cenario: Alocacao, participantes: list[AlocacaoUnidade]
    ) -> EntradaAlocacao:
        """
        Traduz o cenário salvo na entrada do motor.

        Os ids do domínio são os próprios ids do banco — sem tabela de-para, o
        resultado volta pronto para gravar.
        """
        clinicas = []
        for unidade in participantes:
            demanda = [0] * NUM_TURNOS
            for item in unidade.demandas:
                demanda[indice_turno(item.dia_semana, item.turno)] = item.quantidade
            clinicas.append(
                Clinica(id=unidade.id, nome=unidade.unidade_nome, demanda=tuple(demanda))
            )

        pavimentos = tuple(
            PavimentoDominio(
                id=p.id, nome=p.nome_completo, capacidade=p.capacidade
            )
            for p in cenario.pavimentos
        )

        ids_participantes = {u.id for u in participantes}
        obrigatorias: dict[int, int] = {}
        afinidade: dict[tuple[int, int], float] = {}
        for restricao in cenario.restricoes:
            if restricao.alocacao_unidade_id not in ids_participantes:
                continue
            if restricao.tipo == OBRIGATORIO:
                obrigatorias[restricao.alocacao_unidade_id] = restricao.pavimento_id
            elif restricao.tipo == PREFERENCIAL:
                chave = (restricao.alocacao_unidade_id, restricao.pavimento_id)
                afinidade[chave] = (
                    afinidade.get(chave, 0.0) + PESO_PREFERENCIA_MANUAL
                )

        return EntradaAlocacao(
            clinicas=tuple(clinicas),
            pavimentos=pavimentos,
            obrigatorias=obrigatorias,
            afinidade=afinidade,
        )

    async def _gravar(self, cenario: Alocacao, resultado: ResultadoAlocacao) -> None:
        """
        Substitui o resultado anterior — reexecutar não acumula linhas.

        Trabalhamos pela coleção da unidade, e não com um DELETE em massa: o
        DELETE apagaria as linhas no banco mas deixaria a coleção já carregada
        na sessão com dados velhos, e quem executasse a alocação e lesse o
        resultado em seguida veria o estado errado. Limpar a coleção deixa o
        cascade delete-orphan apagar as linhas e mantém memória e banco juntos.
        """
        por_id = {u.id: u for u in cenario.unidades}

        for unidade in cenario.unidades:
            unidade.resultados.clear()
            # Unidades que não participam perdem o pavimento: manter o antigo
            # daria a impressão de que elas ainda estão alocadas em algum lugar.
            if not unidade.participa:
                unidade.pavimento_alocado_id = None

        # Descarrega os DELETEs antes de inserir. Sem este flush, o SQLAlchemy
        # pode emitir o INSERT da linha nova antes do DELETE da antiga e esbarrar
        # na chave única (unidade, dia, turno) ao reexecutar a alocação.
        await self.sessao.flush()

        for item in resultado.por_clinica:
            unidade = por_id.get(item.clinica_id)
            if unidade is None:
                continue
            unidade.pavimento_alocado_id = item.pavimento_id

            for indice, (dia, periodo) in enumerate(TURNOS):
                alocada = item.alocado[indice]
                nao_alocada = item.nao_alocado[indice]
                if alocada == 0 and nao_alocada == 0:
                    continue
                unidade.resultados.append(
                    AlocacaoResultado(
                        alocacao_unidade_id=unidade.id,
                        dia_semana=dia,
                        turno=periodo,
                        qtd_alocada=alocada,
                        qtd_nao_alocada=nao_alocada,
                    )
                )

        await self.sessao.flush()

    # -- Etapa 6 -----------------------------------------------------------

    async def ajustar(
        self, cenario: Alocacao, unidade_id: int, dia: str, turno: str, qtd_alocada: int
    ) -> AlocacaoResultado:
        """
        Ajuste manual de um turno: transfere "não alocação" dentro do pavimento.

        A demanda é fixa, então o que o gestor decide é a divisão entre alocado e
        não alocado. O total do pavimento no turno não pode passar da capacidade
        — senão o ajuste criaria salas que não existem.
        """
        unidade = next((u for u in cenario.unidades if u.id == unidade_id), None)
        if unidade is None:
            raise ValueError(f"unidade {unidade_id} não pertence a este cenário")
        if qtd_alocada < 0:
            raise ValueError("a quantidade alocada não pode ser negativa")

        registro = next(
            (
                r
                for r in unidade.resultados
                if r.dia_semana == dia and r.turno == turno
            ),
            None,
        )
        if registro is None:
            raise ValueError(
                f"{unidade.unidade_nome} não tem resultado em {dia}/{turno}"
            )

        demanda = registro.qtd_alocada + registro.qtd_nao_alocada
        if qtd_alocada > demanda:
            raise ValueError(
                f"não é possível alocar {qtd_alocada}: a demanda em {dia}/{turno} "
                f"é de {demanda}"
            )

        pavimento = next(
            (p for p in cenario.pavimentos if p.id == unidade.pavimento_alocado_id),
            None,
        )
        if pavimento is not None:
            ocupado_por_outras = sum(
                r.qtd_alocada
                for outra in cenario.unidades
                if outra.id != unidade_id
                and outra.pavimento_alocado_id == pavimento.id
                for r in outra.resultados
                if r.dia_semana == dia and r.turno == turno
            )
            if ocupado_por_outras + qtd_alocada > pavimento.capacidade:
                disponivel = pavimento.capacidade - ocupado_por_outras
                raise ValueError(
                    f"{pavimento.nome_completo} só tem {disponivel} estações livres "
                    f"em {dia}/{turno}"
                )

        registro.qtd_alocada = qtd_alocada
        registro.qtd_nao_alocada = demanda - qtd_alocada

        await self.processo.registrar_alteracao(cenario, ETAPA_AJUSTES)
        return registro
