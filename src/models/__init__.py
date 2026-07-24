"""
Modelos ORM do SAA.

Importar este pacote registra todas as tabelas em `Base.metadata` — é do que
o `create_all` do startup e o autogenerate do Alembic dependem para enxergar
o esquema.
"""

from src.models.saa import (
    Alocacao,
    AlocacaoEtapa,
    AlocacaoResultado,
    AlocacaoUnidade,
    GradeDemanda,
    GradeSlot,
    Pavimento,
    PavimentoCatalogo,
    Restricao,
    UnidadeCatalogo,
)

__all__ = [
    "Alocacao",
    "AlocacaoEtapa",
    "AlocacaoResultado",
    "AlocacaoUnidade",
    "GradeDemanda",
    "GradeSlot",
    "Pavimento",
    "PavimentoCatalogo",
    "Restricao",
    "UnidadeCatalogo",
]
