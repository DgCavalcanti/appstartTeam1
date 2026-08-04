"""
visualizacao_service.py — O painel consolidado, somente leitura.

Não altera nada: apenas agrega o resultado de um cenário já alocado em três
recortes — indicadores gerais, ocupação por pavimento e panorama por turno.

Os números de sala e as porcentagens convertem estações de volta para salas
físicas, como pede a seção 14: o motor raciocina em estações, mas o gestor
pensa em salas.

Referência: SAA_Arquitetura.pdf, seções 7, 9 e 14.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entidades import NUM_TURNOS, OBRIGATORIO, TURNOS, indice_turno
from src.domain.processo import DESATUALIZADA, PREENCHIDA
from src.models.saa import Alocacao
from src.services.processo_service import ETAPA_EXECUCAO, ProcessoService

logger = logging.getLogger(__name__)


class VisualizacaoService:
    def __init__(self, sessao: AsyncSession) -> None:
        self.sessao = sessao

    def disponivel(self, cenario: Alocacao) -> bool:
        """
        Só há o que visualizar depois que o motor rodou.

        Vale mesmo quando a execução está desatualizada: o painel mostra o
        último resultado, e o stepper já avisa que ele pode não valer mais.
        """
        etapa = ProcessoService(self.sessao).etapa(cenario, ETAPA_EXECUCAO)
        return etapa.status in (PREENCHIDA, DESATUALIZADA)

    def montar(self, cenario: Alocacao) -> dict:
        """O painel completo. Levanta ValueError se o cenário não foi alocado."""
        if not self.disponivel(cenario):
            raise ValueError(
                "o cenário ainda não foi alocado: não há o que visualizar"
            )

        por_pavimento = self._por_pavimento(cenario)
        por_turno = self._por_turno(cenario)
        por_clinica = self._por_clinica(cenario)

        return {
            "id": cenario.id,
            "nome": cenario.nome,
            "status": cenario.status,
            "desatualizada": self._execucao_desatualizada(cenario),
            "turnos": [{"dia": d, "periodo": t} for d, t in TURNOS],
            "resumo": self._resumo(cenario, por_pavimento, por_clinica),
            "por_pavimento": por_pavimento,
            "por_turno": por_turno,
            "por_clinica": por_clinica,
        }

    # -- Recortes ----------------------------------------------------------

    def _por_pavimento(self, cenario: Alocacao) -> list[dict]:
        """
        O recorte que a tela de visualização usa como eixo principal (seção 3
        do pedido de melhoria): "quais unidades funcionais estão em cada
        pavimento?" — com ocupação por turno, capacidade, salas abertas,
        demanda não alocada e alertas.
        """
        # Unidades com obrigatoriedade — usado para diferenciar, no alerta, uma
        # sobra "estrutural" (a obrigatoriedade force a entrar mesmo sem
        # espaço) de uma sobra comum de empacotamento.
        obrigatorias_por_unidade = {
            r.alocacao_unidade_id: r.pavimento_id
            for r in cenario.restricoes
            if r.tipo == OBRIGATORIO
        }

        painel = []
        for pavimento in cenario.pavimentos:
            ocupantes = [
                u
                for u in cenario.unidades
                if u.participa and u.pavimento_alocado_id == pavimento.id
            ]

            ocupacao = [0] * NUM_TURNOS
            nao_alocado = [0] * NUM_TURNOS
            # Cada clínica deste bloco, com sua própria linha de 10 turnos — é o
            # que a visualização desenha como faixa dentro do card do bloco.
            clinicas = []
            for unidade in ocupantes:
                c_alocado = [0] * NUM_TURNOS
                c_nao_alocado = [0] * NUM_TURNOS
                for item in unidade.resultados:
                    i = indice_turno(item.dia_semana, item.turno)
                    c_alocado[i] = item.qtd_alocada
                    c_nao_alocado[i] = item.qtd_nao_alocada
                    ocupacao[i] += item.qtd_alocada
                    nao_alocado[i] += item.qtd_nao_alocada
                clinicas.append(
                    {
                        "nome": unidade.unidade_nome,
                        "alocado": c_alocado,
                        "nao_alocado": c_nao_alocado,
                        "total_alocado": sum(c_alocado),
                        "total_nao_alocado": sum(c_nao_alocado),
                    }
                )
            # As com sobra primeiro — é o que o gestor precisa olhar; depois nome.
            clinicas.sort(key=lambda c: (-c["total_nao_alocado"], c["nome"]))

            capacidade = pavimento.capacidade
            salas_por_turno = [pavimento.salas_em_uso(q) for q in ocupacao]
            pico = max(ocupacao) if ocupacao else 0
            total_nao_alocado = sum(nao_alocado)

            # Unidades obrigatórias deste pavimento que ficaram com sobra —
            # é a "restrição obrigatória problemática" que o gestor precisa ver.
            obrigatorias_com_sobra = sorted(
                u.unidade_nome
                for u in ocupantes
                if obrigatorias_por_unidade.get(u.id) == pavimento.id
                and sum(item.qtd_nao_alocada for item in u.resultados) > 0
            )

            alertas = []
            if obrigatorias_com_sobra:
                alertas.append(
                    {
                        "tipo": "obrigatoriedade_problematica",
                        "mensagem": (
                            "Obrigatoriedade força "
                            f"{', '.join(obrigatorias_com_sobra)} neste pavimento, "
                            f"mas sobram {total_nao_alocado} grade(s) sem sala."
                        ),
                    }
                )
            elif total_nao_alocado:
                alertas.append(
                    {
                        "tipo": "excesso",
                        "mensagem": (
                            f"Capacidade excedida: {total_nao_alocado} grade(s) "
                            "sem sala neste pavimento."
                        ),
                    }
                )

            painel.append(
                {
                    "id": pavimento.id,
                    # `andar` agrupa os blocos (o "pavimento" do prédio); `bloco`
                    # e `pavimento` são os rótulos curtos que a tela desenha.
                    "andar": pavimento.andar,
                    "bloco": pavimento.bloco,
                    "pavimento": pavimento.nome,
                    "nome": pavimento.nome_completo,
                    "capacidade": capacidade,
                    "salas_abertas": pavimento.salas_abertas,
                    "ocupacao": ocupacao,
                    "nao_alocado": nao_alocado,
                    "total_nao_alocado": total_nao_alocado,
                    "salas_por_turno": salas_por_turno,
                    "salas_no_pico": max(salas_por_turno) if salas_por_turno else 0,
                    "ocupacao_media_pct": self._pct(sum(ocupacao), capacidade * NUM_TURNOS),
                    "ocupacao_pico_pct": self._pct(pico, capacidade),
                    "clinicas": clinicas,
                    "alertas": alertas,
                }
            )
        return painel

    def _por_turno(self, cenario: Alocacao) -> list[dict]:
        alocado = [0] * NUM_TURNOS
        nao_alocado = [0] * NUM_TURNOS
        for unidade in cenario.unidades:
            if not unidade.participa:
                continue
            for item in unidade.resultados:
                i = indice_turno(item.dia_semana, item.turno)
                alocado[i] += item.qtd_alocada
                nao_alocado[i] += item.qtd_nao_alocada

        capacidade_total = sum(p.capacidade for p in cenario.pavimentos)
        return [
            {
                "dia": dia,
                "periodo": periodo,
                "alocado": alocado[i],
                "nao_alocado": nao_alocado[i],
                "demanda": alocado[i] + nao_alocado[i],
                "ocupacao_pct": self._pct(alocado[i], capacidade_total),
            }
            for i, (dia, periodo) in enumerate(TURNOS)
        ]

    def _por_clinica(self, cenario: Alocacao) -> list[dict]:
        pavimentos = {p.id: p for p in cenario.pavimentos}
        clinicas = []
        for unidade in cenario.unidades:
            if not unidade.participa:
                continue
            alocado = [0] * NUM_TURNOS
            nao_alocado = [0] * NUM_TURNOS
            for item in unidade.resultados:
                i = indice_turno(item.dia_semana, item.turno)
                alocado[i] = item.qtd_alocada
                nao_alocado[i] = item.qtd_nao_alocada

            pavimento = pavimentos.get(unidade.pavimento_alocado_id or -1)
            clinicas.append(
                {
                    "nome": unidade.unidade_nome,
                    # Bloco e pavimento (nome curto) separados, para colunas e
                    # filtros distintos na tela; o completo fica para tooltip.
                    "bloco": pavimento.bloco if pavimento else None,
                    "pavimento": pavimento.nome if pavimento else None,
                    "pavimento_completo": pavimento.nome_completo if pavimento else None,
                    "alocado": alocado,
                    "nao_alocado": nao_alocado,
                    "total_alocado": sum(alocado),
                    "total_nao_alocado": sum(nao_alocado),
                }
            )
        # As com sobra primeiro — é o que o gestor precisa olhar.
        clinicas.sort(key=lambda c: (-c["total_nao_alocado"], c["nome"]))
        return clinicas

    def _resumo(
        self, cenario: Alocacao, por_pavimento: list[dict], por_clinica: list[dict]
    ) -> dict:
        total_alocado = sum(c["total_alocado"] for c in por_clinica)
        total_nao_alocado = sum(c["total_nao_alocado"] for c in por_clinica)
        usados = [p for p in por_pavimento if p["clinicas"]]

        salas_no_pico = sum(p["salas_no_pico"] for p in por_pavimento)
        salas_totais = sum(p["salas_abertas"] for p in por_pavimento)

        return {
            "total_alocado": total_alocado,
            "total_nao_alocado": total_nao_alocado,
            "total_demanda": total_alocado + total_nao_alocado,
            "clinicas_alocadas": len(por_clinica),
            "clinicas_com_sobra": sum(
                1 for c in por_clinica if c["total_nao_alocado"] > 0
            ),
            "pavimentos_usados": len(usados),
            "pavimentos_totais": len(por_pavimento),
            "salas_no_pico": salas_no_pico,
            "salas_totais": salas_totais,
            "pavimentos_com_alerta": sum(1 for p in por_pavimento if p["alertas"]),
            # Ponderada por capacidade (Fase 2), não média aritmética simples
            # dos pavimentos usados: um pavimento de 40 estações a 90% pesa
            # mais no indicador geral do que um de 5 estações a 90% — média
            # simples tratava os dois como iguais e escondia desequilíbrio.
            "ocupacao_media_pct": self._pct(
                sum(sum(p["ocupacao"]) for p in usados),
                sum(p["capacidade"] for p in usados) * NUM_TURNOS,
            ),
        }

    # -- Auxiliares --------------------------------------------------------

    def _execucao_desatualizada(self, cenario: Alocacao) -> bool:
        etapa = ProcessoService(self.sessao).etapa(cenario, ETAPA_EXECUCAO)
        return etapa.status == DESATUALIZADA

    @staticmethod
    def _pct(parte: int, total: int) -> float:
        return round(100 * parte / total, 1) if total else 0.0
