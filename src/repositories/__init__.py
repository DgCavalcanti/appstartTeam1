"""
Repositórios — o único ponto do sistema que fala com o banco.

Traduzem entidades de domínio ⇄ tabelas, isolando o SQLite do resto. Nenhuma
regra de negócio mora aqui.
"""

from src.repositories.alocacao_repository import AlocacaoRepository, PavimentoEntrada
from src.repositories.catalogo_repository import CatalogoRepository

__all__ = ["AlocacaoRepository", "CatalogoRepository", "PavimentoEntrada"]
