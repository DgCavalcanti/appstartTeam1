"""
Motor de alocação do SAA.

A estratégia fica atrás da interface `SolverAlocacao`, de modo que a heurística
possa ser trocada por um solver exato (OR-Tools CP-SAT) sem tocar em API, banco
ou telas.
"""

from src.domain.alocacao.solver import (
    EntradaAlocacao,
    OcupacaoPavimento,
    ResultadoAlocacao,
    ResultadoClinica,
    SolverAlocacao,
)
from src.domain.alocacao.heuristica import SolverHeuristico, repartir_turno

__all__ = [
    "EntradaAlocacao",
    "OcupacaoPavimento",
    "ResultadoAlocacao",
    "ResultadoClinica",
    "SolverAlocacao",
    "SolverHeuristico",
    "repartir_turno",
]
