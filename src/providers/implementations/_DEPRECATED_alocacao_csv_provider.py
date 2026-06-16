"""
_DEPRECATED_alocacao_csv_provider.py — CÓDIGO MORTO, NÃO IMPORTADO EM NENHUM LUGAR.

Este módulo definia AlocacaoCsvProvider, uma implementação CSV+SQLite legada do
provider de alocação. Foi totalmente substituído por
src/providers/implementations/alocacao_saa_csv_provider.py (AlocacaoSaaCsvProvider),
que é o provider realmente usado por src/routers/alocacao.py.

Por que foi desativado (renomeado com prefixo _DEPRECATED_ em vez de simplesmente
apagado — a ferramenta de auditoria não teve permissão de exclusão de arquivo no
ambiente de execução; recomenda-se remover este arquivo no próximo commit):

  1. Zero referências em src/, tests/ ou scripts — confirmado via grep em toda a
     árvore do projeto antes da depreciação.
  2. Usava o esquema de dados ANTIGO de Sala/Alocacao (tem_equipamento, acessivel,
     id_grade, id_sala — todos com tipos int), incompatível com o esquema ATUAL em
     src/models/schemas.py (equipamentos: list[str], acessibilidade: bool,
     grade_id/sala_id: str). Se fosse importado hoje, falharia em tempo de execução
     ao tentar validar contra os Pydantic models atuais.
  3. Implementava AlocacaoProviderInterface (também depreciada nesta auditoria —
     ver src/providers/interfaces/_DEPRECATED_alocacao_provider_interface.py),
     que por sua vez não é mais implementada por nenhum provider ativo.

Ação recomendada: excluir este arquivo do repositório.
"""
