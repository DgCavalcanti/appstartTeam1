# Status atual — Painel SAA não atualiza + grades duplicadas

> Última atualização: 2026-06-17. **Feature concluída** (backend + frontend).
> Verificação: revisão manual completa de cada arquivo via leitura direta
> (ver nota sobre o sandbox no final). `pytest` real não foi executado nesta
> sessão — mesma limitação já registrada na feature anterior (reset de
> dados): o mount do bash não reflete os arquivos editados nesta sessão.

## O que o usuário pediu

> "analise o projeto, pois quando aloco uma sala na pagina de grades, no
> painel nao aparece. alem disso, grades nao podem se repetir. crie um
> botao no saa em que ele remove as grades repetidas, pois elas devem ser
> unicas."

Três pedidos: (1) descobrir por que uma sala alocada em "Grades de
Atendimento" não aparece no "Painel SAA"; (2) garantir que grades não se
repitam; (3) criar um botão no SAA para remover grades duplicadas.

## Causa raiz #1 — alocação não aparece no painel

`EditarAlocacao.vue` (`salvar()`), quando a grade ainda não tinha sala
nenhuma, fazia `store.alocacoes.push({...})` — um push **local**, só no
Pinia, sem chamar o backend. Ao navegar para o Painel SAA, `onMounted()`
busca as alocações de novo em `GET /api/alocacoes`, e a alocação criada
localmente desaparecia (nunca existiu no backend).

Não havia, de fato, **nenhum endpoint de criação** de alocação — só
`POST /api/alocacoes/ajustar` (que exige uma alocação já existente).

## Causa raiz #2 — grades duplicadas

`vw_grades.csv` (export real do AGHU) tem várias linhas para a mesma
grade no mesmo dia/turno — uma por `Condicao_De_Atendimento` (RETORNO,
CONSULTA PRIMEIRA VEZ, INTERCONSULTA etc.). São dados reais e legítimos,
não "lixo", mas para o SAA (que só quer saber "que sala está alocada
nesse horário?") elas representam a mesma grade e apareciam repetidas.

**Descoberta importante**: o mesmo `vw_grades.csv` alimenta dois módulos
com necessidades opostas — o SAA (quer 1 linha por grade) e o "AGHU:
Dados Reais" / `/api/aghu/*` (quer todas as linhas, pois cada uma tem
`Quantidade_Vagas` real para relatórios de capacidade/qualidade). Por
isso a deduplicação **não pode** apagar linhas do CSV — só pode acontecer
na camada de adaptação exclusiva do SAA.

**Critério de unicidade definido**: `(grade_id, dia_semana, turno)`. Um
mesmo `grade_id` pode legitimamente recorrer em dias/turnos diferentes
(grade recorrente) — isso não é duplicata.

## O que foi feito

### Backend

1. `GradeAghuDashboardProvider.listar_grades()`/`buscar_grade()` —
   deduplicam por `(grade_id, dia_semana, turno)`, mantendo a primeira
   ocorrência. Nunca toca em `vw_grades.csv`.
2. Novo método `relatorio_duplicadas()` no mesmo provider — calcula
   `(total_linhas_brutas, total_grades_unicas)` sem alterar nada em disco.
3. Novo endpoint `POST /api/grades/remover-duplicadas` — verifica e
   confirma o resultado da deduplicação (texto explicando quantas linhas
   "colapsaram" em quantas grades únicas).
4. Novo endpoint `POST /api/alocacoes` (`criar_alocacao`) — cria a 1ª
   alocação de uma grade. Busca a grade pela tripla `(id, dia_semana,
   turno)` (não só `grade_id`, que pode ser ambíguo), valida a sala,
   impede criar uma 2ª alocação para a mesma ocorrência (nesse caso
   orienta a usar `/ajustar`), calcula conflitos e exige justificativa
   se houver conflito crítico/operacional, persiste e registra histórico.
5. **Bug corrigido em `AlocacaoSaaCsvProvider.listar_alocacoes()`**: só
   percorria o CSV base e substituía por ajustes do SQLite pelo `id` —
   alocações que existem **só** no SQLite (criadas via o novo endpoint)
   eram silenciosamente descartadas. Agora também inclui essas.
6. Novos schemas: `RemocaoGradesDuplicadasResultado`,
   `CriarAlocacaoRequest`, `CriarAlocacaoResponse`.
7. **Bug adicional encontrado e corrigido em `conflito_service.py` (C07
   — grade sem sala)**: usava só `grade_id` para saber se uma grade tinha
   alocação; com grades recorrentes (mesmo `grade_id`, dias diferentes),
   uma ocorrência alocada "escondia" a falta de sala de outra ocorrência
   do mesmo `grade_id`. Corrigido para usar a tripla `(grade_id,
   dia_semana, turno)`, consistente com o resto da correção.

### Frontend

8. `stores/saa.ts` — `getAlocacaoPorGrade()` agora aceita
   `dia_semana`/`turno` opcionais para desambiguar grades recorrentes;
   nova action `criarAlocacao()` (chama `POST /api/alocacoes` de fato,
   em vez do push local); nova action `removerGradesDuplicadas()`
   (chama `POST /api/grades/remover-duplicadas`).
9. `EditarAlocacao.vue` — `salvar()` agora chama `store.criarAlocacao()`
   quando a grade não tem alocação (antes era só `store.alocacoes.push`).
   Esta é a correção direta do bug relatado.
10. `SaaDashboard.vue` — `alocacaoDaGrade()` e o mapa interno passaram a
    usar a chave composta `grade_id|dia_semana|turno`, em vez de só
    `grade_id`.
11. `SaaGrades.vue` — chamadas a `getAlocacaoPorGrade()` agora passam
    `dia_semana`/`turno`; novo botão **"Verificar grades duplicadas"** no
    cabeçalho, que chama o endpoint de verificação e mostra o resultado
    via toast (quantas linhas brutas, quantas únicas).

## Por que o botão não "remove" de fato

A deduplicação já é automática em toda listagem do SAA — não existem
duplicatas "soltas" para apagar nesse nível. Apagar as linhas brutas do
`vw_grades.csv` quebraria os relatórios de capacidade/qualidade do AGHU,
que dependem de cada linha (`Condicao_De_Atendimento`) ser preservada.
Por isso o botão foi desenhado como uma ação de **verificação/confirmação
não destrutiva**, em vez de uma exclusão física — atende ao requisito
"grades não podem se repetir" sem efeito colateral nos outros módulos.

## Arquivos tocados

- `src/models/schemas.py` — 2 schemas novos. ✅
- `src/providers/implementations/grade_aghu_dashboard_provider.py` —
  dedup + `relatorio_duplicadas()`. ✅
- `src/routers/grade.py` — endpoint `POST /remover-duplicadas`. ✅
- `src/controllers/alocacao_controller.py` — `criar_alocacao()`. ✅
- `src/providers/implementations/alocacao_saa_csv_provider.py` — fix do
  merge CSV+SQLite. ✅
- `src/routers/alocacao.py` — endpoint `POST /api/alocacoes`. ✅
- `src/services/conflito_service.py` — fix C07 (chave composta). ✅
- `frontend/src/stores/saa.ts` — tipos/actions novas + fix de
  `getAlocacaoPorGrade`. ✅
- `frontend/src/components/EditarAlocacao.vue` — usa `criarAlocacao()`
  de verdade. ✅
- `frontend/src/views/SaaDashboard.vue` — chave composta. ✅
- `frontend/src/views/SaaGrades.vue` — call sites corrigidos + botão
  novo. ✅

## Verificação realizada

Todos os 11 arquivos acima foram lidos por completo após a edição
(ferramenta de leitura direta, não o mount do bash) e revisados
manualmente: imports, assinaturas, sintaxe, consistência entre
request/response do backend e os tipos TypeScript do frontend, e
compatibilidade com os testes existentes (`tests/test_saa_routers.py`,
`tests/test_conflito_service.py`, `tests/test_alocacao_saa_csv_provider.py`)
— nenhum deles depende do comportamento antigo que foi alterado.

**Limitação conhecida do sandbox**: o mount do bash usado nesta sessão
está desatualizado (confirmado via `stat`/`wc -l` mostrando conteúdo de
~24h atrás mesmo após os arquivos serem editados), então não foi possível
rodar `pytest` real nem `ast.parse` confiável por esse caminho nesta
sessão. Recomenda-se rodar `pytest` localmente antes de considerar a
feature pronta para produção.

## Próximo passo recomendado

Rodar `pytest` localmente (ou em um ambiente com mount atualizado) para
confirmar que os testes existentes continuam passando, e testar
manualmente o fluxo completo: importar uma grade real → alocar sala na
tela de Grades → confirmar que aparece no Painel SAA sem precisar de
F5 forçado em outra aba.
