"""
processo.py — O vocabulário das 6 etapas.

Python puro: nomes das etapas, status possíveis e a regra de invalidação. O
orquestrador que aplica essas regras vive na camada de serviços; aqui ficam só
as definições, para que banco, API e telas falem a mesma língua.

Referência: SAA_Arquitetura.pdf, seção 7.
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Status de cada etapa
# ---------------------------------------------------------------------------

#: Ainda não preenchida nesta rodada.
PENDENTE = "pendente"
#: Concluída e coerente com as etapas anteriores.
PREENCHIDA = "preenchida"
#: Uma etapa anterior mudou depois que esta foi feita. O sistema avisa em vez
#: de apagar — o gestor decide se refaz.
DESATUALIZADA = "desatualizada"

STATUS_ETAPA: tuple[str, ...] = (PENDENTE, PREENCHIDA, DESATUALIZADA)


# ---------------------------------------------------------------------------
# Status do cenário como um todo
# ---------------------------------------------------------------------------

RASCUNHO = "rascunho"
EM_ANDAMENTO = "em_andamento"
CONCLUIDA = "concluida"

STATUS_ALOCACAO: tuple[str, ...] = (RASCUNHO, EM_ANDAMENTO, CONCLUIDA)


# ---------------------------------------------------------------------------
# As 6 etapas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Etapa:
    numero: int
    chave: str
    nome: str


ETAPAS: tuple[Etapa, ...] = (
    Etapa(1, "importacao", "Importar grades do AGHU"),
    Etapa(2, "grades", "Validar e ajustar grades"),
    Etapa(3, "panorama", "Panorama de salas"),
    Etapa(4, "restricoes", "Obrigatoriedades e preferências"),
    Etapa(5, "execucao", "Executar algoritmo"),
    Etapa(6, "ajustes", "Ajustes manuais da alocação"),
)

PRIMEIRA_ETAPA: int = ETAPAS[0].numero
ULTIMA_ETAPA: int = ETAPAS[-1].numero

#: Etapas que produzem a alocação. Mexer em qualquer etapa anterior as torna
#: desatualizadas, porque o resultado pode não valer mais.
ETAPAS_DE_RESULTADO: frozenset[int] = frozenset({5, 6})


def etapa_por_numero(numero: int) -> Etapa:
    for etapa in ETAPAS:
        if etapa.numero == numero:
            return etapa
    raise ValueError(
        f"etapa inválida: {numero}. Esperado entre {PRIMEIRA_ETAPA} e {ULTIMA_ETAPA}"
    )


def etapas_invalidadas_por(numero: int) -> frozenset[int]:
    """
    Quais etapas ficam desatualizadas quando a etapa `numero` muda.

    Mexer nas grades (1–2), no panorama de salas (3) ou nas restrições (4)
    invalida a alocação (5–6). A etapa 6 edita diretamente o resultado da 5 e
    pode ser acessada a qualquer momento, sem invalidar nada — é exatamente o
    atalho que o documento pede.
    """
    etapa_por_numero(numero)  # valida
    if numero in ETAPAS_DE_RESULTADO:
        return frozenset()
    return frozenset(n for n in ETAPAS_DE_RESULTADO if n > numero)
