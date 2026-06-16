"""
_DEPRECATED_alocacao_provider_interface.py — CÓDIGO MORTO, NÃO IMPORTADO EM NENHUM LUGAR.

Definia AlocacaoProviderInterface, o contrato ABC legado para providers de
alocação (listar_grades, listar_salas, listar_historico, salvar_alocacoes).

Era implementada apenas por
src/providers/implementations/_DEPRECATED_alocacao_csv_provider.py (também
depreciado nesta auditoria — ver docstring daquele arquivo para detalhes).

O contrato ativo equivalente é AlocacaoSaaProviderInterface, definido em
src/providers/interfaces/historico_provider_interface.py e implementado por
src/providers/implementations/alocacao_saa_csv_provider.py (AlocacaoSaaCsvProvider),
que é o provider realmente usado por src/routers/alocacao.py.

Renomeado com prefixo _DEPRECATED_ em vez de excluído porque a ferramenta de
auditoria não teve permissão de exclusão de arquivo neste ambiente de execução
(restrição do filesystem virtiofs montado). Ação recomendada: excluir este
arquivo do repositório.
"""
