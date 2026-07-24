"""
Pipeline de importação e tratamento de dados (etapa 1).

A importação não é só "ler a planilha": é uma sequência de regras cuja ordem
importa. O resultado é uma demanda limpa e compacta, pronta para o motor.

Os passos 1–8 acontecem em memória, num DataFrame. Só o `grade_slot` (grão do
profissional) e o `grade_demanda` derivado são materializados — as linhas brutas
do AGHU nunca vão para o banco.

Referência: SAA_Arquitetura.pdf, seção 6.
"""

from src.domain.importacao.leitor import ler_planilha
from src.domain.importacao.regras import (
    CONDICOES_SEM_SALA,
    GradeDemanda,
    GradeSlot,
    normalizar,
)
from src.domain.importacao.pipeline import (
    Catalogo,
    RelatorioImportacao,
    ResultadoImportacao,
    executar_pipeline,
    importar,
    para_clinicas,
)

__all__ = [
    "CONDICOES_SEM_SALA",
    "Catalogo",
    "GradeDemanda",
    "GradeSlot",
    "RelatorioImportacao",
    "ResultadoImportacao",
    "executar_pipeline",
    "importar",
    "ler_planilha",
    "normalizar",
    "para_clinicas",
]
