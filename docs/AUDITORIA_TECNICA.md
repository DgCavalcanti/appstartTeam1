# Auditoria Técnica Completa — SAA (Sistema de Apoio à Alocação Ambulatorial)

**Data:** 16/06/2026
**Escopo:** Backend (FastAPI), Frontend (Vue 3 + Vite), configs, dependências, scripts e documentação.
**Metodologia:** leitura integral de todos os módulos de `src/` e `frontend/src/`, análise estática com `ruff`, execução da suíte de testes (`pytest`), build/typecheck do frontend, e verificação cruzada de nomes de campos entre schemas Pydantic, providers CSV/SQL e o frontend (stores Pinia / chamadas Axios).

---

## 1. Resumo Executivo

O projeto está **estruturalmente sólido**: arquitetura em camadas (routers → controllers → providers) é consistente, a suíte de testes passa integralmente, e os fluxos principais (grades, salas, alocações, importação CSV, indicadores AGHU) funcionam de ponta a ponta. Os problemas reais encontrados foram, em sua maioria, **dívida técnica localizada** — código morto desalinhado com o schema atual, uso de `print()` em vez de `logging`, uma rota de fallback ausente no frontend — e não falhas que impeçam a aplicação de rodar localmente hoje.

**O mais grave dos achados** (módulo `alocacao_engine.py` com `ImportError` garantido, ver §3.1) afetava um módulo já documentado como não-importado por nenhum router, portanto não quebrava a aplicação em produção — mas quebraria imediatamente caso alguém o reativasse, o que é exatamente o cenário para o qual ele foi "preservado". Esse e os demais achados abaixo foram corrigidos nesta sessão.

Após as correções: **0 erros de sintaxe/import, 0 testes falhando (107/107 passando), 0 achados de lint não-explicados** (`ruff check` limpo, restando apenas 9 avisos E402 intencionais em `main.py`, documentados em §4.1).

---

## 2. Auditoria de Configuração e Dependências

| Item | Situação |
|---|---|
| `.env.example` | Completo e consistente com as variáveis lidas em `src/auth/auth.py`, `src/main.py` e `src/resources/database.py` (`POSTGRES_DSN`, `SQLITE_DSN`/`APP_DB_URL`, `AD_URL`, `JWT_SECRET`, etc.). |
| `requirements.txt` / `pyproject.toml` | Consistentes entre si (mesmas versões). `requires-python = ">=3.13"` confere com `.python-version` (`3.13`) e com o Python real do `.venv` gerenciado por `uv` (3.13.14) — **não é uma inconsistência**, apenas precisa que o ambiente de execução real use `uv run`/`.venv`, não um Python de sistema diferente. |
| `package.json` (frontend) | Scripts `dev`/`build`/`preview` corretos; dependências Vue 3 + Vite + TypeScript coerentes com o código. |
| `start.sh` / `dev.sh` | Funcionais — checam ferramentas (`node`, `python3`, `uv`, `npm`), sincronizam dependências, e sobem os servidores nas portas documentadas (8000 backend, 5173 Vite). Nenhum erro de sintaxe bash encontrado. |
| `docker-compose.yml` | **Não existe no projeto.** O README e os scripts não fazem referência a Docker, então isso é consistente — não é uma lacuna, apenas confirma que o fluxo de execução é 100% via `uv`/`npm`, não containerizado. |
| README.md | Preciso e atualizado: formatos de CSV, tabela de endpoints AGHU, indicadores calculados e instruções de teste todos conferem com o código atual. |
| **Documentação duplicada/órfã na raiz** | Encontrados `architecture.md`, `architecture_guide.md` e `GEMINI.md` na raiz do projeto, além de `docs/ARCHITECTURE.md` (referenciado pelo README) e `docs/spec/06-arquitetura.md`. Há pelo menos **quatro** documentos de arquitetura distintos, alguns claramente pré-implementação (`docs/spec/06-arquitetura.md` lista arquivos como `dashboard_csv_provider.py` e `DashboardSAA.vue`, que não existem no código atual). Isso não afeta a execução, mas gera confusão sobre qual documento é a fonte da verdade. **Recomenda-se** consolidar em `docs/ARCHITECTURE.md` e mover os demais para uma pasta `docs/legado/` ou removê-los. |

---

## 3. Erros Reais Encontrados e Corrigidos Nesta Sessão

### 3.1. `src/services/alocacao_engine.py` — módulo "preservado para o futuro" estava completamente quebrado

O router `src/routers/alocacao.py` documenta explicitamente: *"O motor `alocacao_engine.py` está preservado como módulo futuro/experimental e não é importado aqui"*. Ao auditar esse módulo isoladamente, no entanto, ele continha **três classes de erro reais**, qualquer uma das quais o tornaria inutilizável no instante em que fosse importado:

1. **`ImportError` garantido** — o módulo importava `ResultadoAlocacao` e `ResultadoMotor` de `src.models.schemas`, mas **essas duas classes nunca existiram nesse arquivo**. Eram usadas para tipar o retorno da função `alocar()`, mas nunca foram definidas em nenhum lugar do projeto.
2. **Campos de schema obsoletos** — o módulo usava `sala.tem_equipamento`, `sala.tem_maca_ginecologica` e `sala.acessivel`, todos de uma versão anterior do schema `Sala`. O schema atual usa `sala.equipamentos: list[str]` e `sala.acessibilidade: bool`. Da mesma forma, usava `aloc.id_grade`/`aloc.id_sala` em vez de `aloc.grade_id`/`aloc.sala_id` (schema `Alocacao` atual).
3. **Type hints incorretos** — várias assinaturas declaravam `set[int]`/`list[int]` para IDs, mas `Grade.id` e `Sala.id` são `str` no schema atual (IDs como `"G001"`, `"S101"`).

**Correção aplicada:**
- Adicionadas as classes `ResultadoAlocacao` e `ResultadoMotor` em `src/models/schemas.py` (alinhadas à convenção de nomenclatura do restante do schema: `grade_id`, não `id_grade`).
- `sala.tem_equipamento` → `bool(sala.equipamentos)` (sala "tem equipamento" se a lista não for vazia).
- `sala.tem_maca_ginecologica` → verificação do item `"maca_ginecologica"` dentro de `sala.equipamentos` (constante `EQUIPAMENTO_MACA_GINECOLOGICA` adicionada para clareza).
- `sala.acessivel` → `sala.acessibilidade` (2 ocorrências).
- `aloc.id_grade`/`aloc.id_sala` → `aloc.grade_id`/`aloc.sala_id`.
- Todos os `set[int]`/`list[int]` relativos a IDs corrigidos para `set[str]`/`list[str]`.
- Placeholders de log `%d` para IDs string corrigidos para `%s`.

**Validação:** o módulo foi executado manualmente com dados de teste (3 grades, 3 salas, 1 histórico) após a correção — produziu alocações corretas, incluindo o bloqueio correto de uma grade de Ginecologia quando a única sala com `maca_ginecologica` já estava ocupada por outra grade. Sem erros de import ou atributo.

### 3.2. Código morto incompatível com o schema atual — removido

Dois arquivos eram **código morto confirmado** (zero referências em `src/`, `tests/` ou scripts, verificado via busca em toda a árvore do projeto) e usavam o mesmo schema obsoleto do item 3.1:

- `src/providers/implementations/alocacao_csv_provider.py` (`AlocacaoCsvProvider`)
- `src/providers/interfaces/alocacao_provider_interface.py` (`AlocacaoProviderInterface`)

Ambos foram totalmente substituídos, na prática, por `alocacao_saa_csv_provider.py` (`AlocacaoSaaCsvProvider`) e pela interface `AlocacaoSaaProviderInterface` (definida em `historico_provider_interface.py`), que são os componentes realmente usados por `src/routers/alocacao.py`.

**Limitação técnica encontrada:** o ambiente de execução usado para esta auditoria não tem permissão de exclusão de arquivo no sistema de arquivos do projeto (montagem `virtiofs`/`fuseblk` — operações de `unlink` são bloqueadas, embora escrita e renomeação funcionem normalmente). Por isso, **os dois arquivos foram renomeados com o prefixo `_DEPRECATED_`** e seu conteúdo substituído por um docstring explicando o motivo da depreciação e apontando para os substitutos ativos. **Ação recomendada:** excluir `src/providers/implementations/_DEPRECATED_alocacao_csv_provider.py` e `src/providers/interfaces/_DEPRECATED_alocacao_provider_interface.py` do repositório (um simples `git rm` resolve, já que o ambiente local não tem essa restrição).

### 3.3. `print()` em vez de `logging` — backend inteiro

`src/auth/auth.py` (7 ocorrências) e `src/main.py` (9 ocorrências) usavam `print()` para mensagens de status, autenticação e ciclo de vida da aplicação, enquanto o restante do backend (services, providers) usa o módulo `logging` de forma consistente. Isso significa que essas mensagens não respeitavam `LOG_LEVEL`, não eram formatadas/timestampadas como o resto dos logs, e se perdiam em ambientes que capturam apenas saída de log estruturada.

**Correção aplicada:** todas as 16 chamadas `print()` substituídas por `logger.info(...)` / `logger.warning(...)` equivalentes, com `logger = logging.getLogger(__name__)` adicionado a ambos os módulos.

### 3.4. Frontend: rota desconhecida não tinha fallback

`frontend/src/router/index.ts` não tinha uma rota catch-all. Qualquer URL inválida (erro de digitação, link quebrado, parâmetro malformado) resultava em uma página em branco em vez de redirecionar o usuário para algum lugar útil.

**Correção aplicada:** adicionada a rota `{ path: '/:pathMatch(.*)*', name: 'NotFound', redirect: '/' }` ao final da tabela de rotas.

### 3.5. Limpeza de lint menor (ruff)

Corrigidos durante esta sessão (além dos itens acima):
- Variável ambígua `l` (PEP8 E741 — fácil de confundir com `1`/`I`) renomeada para `linha` em `src/services/capacidade_service.py`, `src/services/qualidade_dados_service.py` e `src/providers/implementations/consulta_aghu_csv_provider.py` (9 ocorrências totais, todas dentro de list/generator comprehensions de escopo local — renomeação segura, sem mudança de comportamento).
- `src/providers/implementations/paciente_csv_provider.py`: variável `f` não utilizada em `with open(...) as f: pass` — removido o `as f` (apenas verificação de existência do arquivo).
- Import não utilizado (`ruff --fix`, sessão anterior) em `src/routers/grade.py` (`Path`) e `src/providers/implementations/historico_sqlite_provider.py` (`datetime`).

---

## 4. Achados Documentados (Não Corrigidos — Intencionais ou Fora do Escopo de "Bug")

### 4.1. `E402` em `src/main.py` — intencional, não é um bug

`ruff` aponta 9 ocorrências de "module level import not at top of file" em `main.py`. Isso é **necessário, não um erro**: `load_dotenv()` precisa rodar antes de qualquer `import` de módulo que leia variáveis de ambiente no momento da importação (ex.: `JWT_SECRET = os.getenv(...)` em `auth.py`, executado na importação do router). Mover os imports para o topo do arquivo quebraria o carregamento das variáveis de ambiente. Recomenda-se manter como está, ou suprimir explicitamente com `# noqa: E402` linha a linha para deixar a intenção clara ao próximo desenvolvedor.

### 4.2. Build do frontend (`npm run build`) falha *neste ambiente de sandbox* — não é um bug do projeto

Durante a verificação anterior desta auditoria, `npm run build` (Vite/Rollup) e o binário do `esbuild` apresentaram `SIGBUS`/"Bus error" no ambiente Linux isolado usado para a análise. A causa raiz identificada: o diretório do projeto está montado via `virtiofs` (passthrough de pasta compartilhada Windows→VM), e os binários nativos do Rollup/esbuild (`.node`/mmap) não toleram esse tipo de sistema de arquivos. `vue-tsc` (typecheck puro, sem binário nativo) funciona normalmente. **Isso não acontece em uma máquina real do desenvolvedor** (sem a camada virtiofs) — é um artefato do ambiente de auditoria, não um defeito do projeto.

### 4.3. `Pacientes.vue` — único componente que não usa o padrão de store Pinia

Todo o módulo SAA (`stores/saa.ts`, `stores/aghu.ts`, `stores/auth.ts`) centraliza chamadas de API em stores Pinia. `frontend/src/views/Pacientes.vue` é a única view que chama `api.get(...)` diretamente no componente. Funciona corretamente, mas é uma inconsistência arquitetural que vale a pena alinhar caso o padrão de store seja a convenção pretendida para o projeto.

### 4.4. `Pacientes.vue` — botões "Editar" e "Excluir" são decorativos

`editPaciente()` e `deletePaciente()` apenas disparam um toast (`"Editando paciente: X"` / `"Deletando paciente: X"`) e não chamam nenhuma API. Isso é coerente com o backend: `src/routers/paciente.py` só expõe `GET /api/pacientes` e `GET /api/pacientes/{codigo}` — não há rotas `PUT`/`DELETE`. **Não é um bug** (claramente um placeholder de MVP), mas é importante destacar para a apresentação de Demo Day: clicar em "Excluir" não excluirá nada de fato, e isso pode gerar confusão se não for sinalizado ao público.

### 4.5. `src/providers/interfaces/historico_provider_interface.py` — nome do arquivo não reflete o conteúdo

Esse arquivo define **duas** interfaces: `AlocacaoSaaProviderInterface` (a interface ativa de alocação — não confundir com a `AlocacaoProviderInterface` legada, removida no §3.2) e `HistoricoProviderInterface`. O nome do arquivo sugere que ele trata apenas de histórico. Sugestão: renomear para algo como `alocacao_e_historico_provider_interface.py`, ou separar em dois arquivos, na próxima refatoração — não corrigido nesta sessão por ser puramente cosmético e por risco de quebrar imports existentes sem benefício funcional imediato.

### 4.6. Documentação de especificação (`docs/spec/`) reflete um modelo de dados anterior

`docs/spec/04-modelo-dados.md` e `docs/REQUISITOS.md` descrevem o modelo de dados antigo (`id_grade`/`id_sala` como `int`, `tem_equipamento`, `acessivel`) — o mesmo modelo que causava os bugs corrigidos no §3.1–3.2. Esses documentos não são consumidos pelo código (são specs de planejamento), então não foram editados nesta auditoria, mas representam dívida de documentação: um novo desenvolvedor que ler `docs/spec/` antes do código terá um modelo mental desatualizado.

---

## 5. Resultado da Verificação

```
ruff check src/ main.py     → 9 avisos (todos E402 intencionais, ver §4.1); 0 erros reais
pytest tests/ -v             → 107 passed, 0 failed
python -c "import src.main" → OK (20 rotas registradas, app sobe sem erro)
```

---

## 6. Conclusão e Prontidão para Demo Day

A aplicação **roda localmente sem erros bloqueantes** e a suíte de testes está 100% verde. Os problemas reais encontrados eram dívida técnica concentrada em código não-exposto por nenhum endpoint (módulo experimental de alocação automática) e detalhes de qualidade (logging, lint, rota de fallback) — nada que impedisse `npm install`/`npm run dev`/`uv run uvicorn` de funcionar. Os pontos levantados na seção 4 não bloqueiam a entrega, mas vale alinhar a expectativa sobre o que é funcional (CRUD de pacientes é somente leitura) e sobre qual documento de arquitetura é a referência oficial antes da apresentação.

### Prioridade sugerida para próximos passos
1. Excluir os dois arquivos `_DEPRECATED_*` do repositório (`git rm`), já que a exclusão real não foi possível neste ambiente.
2. Consolidar a documentação de arquitetura duplicada (raiz vs. `docs/`).
3. Decidir se `Pacientes.vue` deve migrar para o padrão de store Pinia e se os botões de Editar/Excluir devem ser implementados ou removidos antes da demo.

---

## 7. Atualização da Auditoria — Reforços de Backend e Revisão Completa do Frontend

**Data desta atualização:** 16/06/2026 (sessão de continuação da auditoria original, seções 1–6).
**Escopo desta atualização:** hardening adicional do backend (migração Alembic, sessão AGHU, documentação de setup/Docker) e revisão linha a linha de **todo** o `frontend/src` (35 arquivos: views, componentes, stores, router, services, configs de build) que ainda não havia sido coberta em detalhe nas seções 1–6.

### 7.1. Backend — correções adicionais

| # | Arquivo | Problema | Correção aplicada |
|---|---|---|---|
| 1 | `alembic/versions/8a2efbe37bb6_add_groups_to_refresh_token.py` | A migração chamada "add groups to refresh token" na verdade executava `op.drop_table('refresh_tokens')` — ou seja, **uma migração com esse nome apagaria a tabela inteira (3 índices incluídos)** em vez de adicionar a coluna `groups` que o modelo (`src/models/refresh_token.py`) já declara. Rodar `alembic upgrade head` em qualquer ambiente novo destruiria a tabela de refresh tokens. | Substituído por `op.add_column('refresh_tokens', sa.Column('groups', sa.JSON(), nullable=True))`, com `downgrade()` simétrico (`drop_column`). |
| 2 | `src/resources/database.py` (`get_aghu_db_session`) | Quando `POSTGRES_DSN` não está configurado, `app.state.aghu_db` nunca é criado no `lifespan` (ver `main.py`). Qualquer endpoint AGHU chamado nessas condições gerava `AttributeError`/`NoneType has no attribute...` não tratado — um 500 genérico sem explicação. | Passou a verificar explicitamente `getattr(request.app.state, "aghu_db", None)` e levantar `HTTPException(503, "Banco de dados AGHU (PostgreSQL) não configurado. Defina POSTGRES_DSN no .env.")` — erro claro e correto semanticamente (503, não 500). |
| 3 | `.env.example`, `docs/SETUP.md` | A variável `PACIENTE_PROVIDER_TYPE` (usada por `src/providers/` para escolher entre provider CSV/Postgres de pacientes) não estava documentada, então um novo desenvolvedor não saberia que ela existe nem qual valor usar localmente. | Adicionada a variável com valor padrão `CSV` e comentário explicando os valores válidos (`postgres`, `csv`). |
| 4 | `README.md` / `docs/SETUP.md` (Docker) | A documentação de Docker não explicava que `./app.db` é montado como **bind mount de arquivo** pelo `docker compose`, o que falha na primeira execução em hosts onde o arquivo ainda não existe (Docker cria um **diretório** `app.db/` em vez de um arquivo, e o SQLite falha ao abrir). | Adicionada instrução explícita para criar o arquivo vazio antes do primeiro `docker compose up` (`touch app.db` / `New-Item -ItemType File app.db` no Windows). |

### 7.2. Frontend — bugs reais corrigidos

A revisão cobriu os 35 arquivos de `frontend/src` (App.vue, main.ts, 4 stores Pinia, `services/api.ts`, router, 2 layouts, 15 views, 12 componentes) mais `package.json`, `vite.config.ts`, `tsconfig*.json` e `index.css`. Dois bugs reais de lógica foram encontrados e corrigidos:

**a) `Login.vue` redirecionava sempre para `/admin` após o login.**
Qualquer usuário autenticado sem privilégio de administrador caía direto na tela "Acesso Negado" imediatamente após logar com sucesso — mesmo tendo digitado credenciais corretas. Era um placeholder esquecido (o próprio código tinha o comentário `// Ou para onde você quiser redirecionar após o login`). **Corrigido:** redireciona para `/` (Home), acessível a qualquer usuário autenticado.

**b) Cinco telas do módulo SAA nunca buscavam dados da API ao montar.**
`SaaDashboard.vue`, `SaaGrades.vue`, `SaaSalas.vue`, `SaaAlocacoes.vue` e `SaaHistorico.vue` não tinham nenhum hook `onMounted` chamando as actions do store (`buscarSalas`, `buscarGrades`, `buscarAlocacoes`, `buscarConflitos`, `buscarResumoDashboard`, `buscarHistorico`). Essas telas só exibiam dados se o usuário tivesse passado por `SaaImportar.vue` (que popula o store Pinia) **na mesma sessão de navegação** — em qualquer acesso direto a uma URL (`/saa`, `/saa/grades`, etc.) ou simples F5/refresh da página, o Pinia reinicia em memória e a tela inteira aparecia vazia, mesmo com dados reais persistidos no backend (confirmado via `data/salas.csv`, `data/alocacoes.csv`, etc., que existem e têm conteúdo). Esse é, em volume de tela afetada, **o bug de maior impacto encontrado em toda a auditoria**: praticamente todo o módulo SAA (painel, grades, salas, alocações, histórico) parecia quebrado/vazio em um cenário de uso completamente normal (abrir o link direto, ou atualizar a página).

O padrão correto já existia no próprio projeto — as 3 telas do módulo AGHU (`SaaCapacidade.vue`, `SaaConsultas.vue`, `SaaQualidadeDados.vue`) já implementavam `onMounted` corretamente, inclusive com comentários no código explicando exatamente esse mesmo risco. **Corrigido:** adicionado `onMounted(async () => { await Promise.all([...]) })` chamando as actions de busca relevantes nas 5 telas afetadas, seguindo o padrão já estabelecido pelas telas AGHU.

### 7.3. Achados documentados (não corrigidos)

| Item | Situação |
|---|---|
| `EditarAlocacao.vue` — criação de alocação "local-only" | Quando uma grade ainda não tem alocação, o componente insere um objeto sintético direto no array `store.alocacoes` do Pinia, sem persistir no backend (comentário original já assume isso: "sem persistência no MVP"). Limitação intencional de escopo do MVP, não um bug introduzido. Com a correção do item 7.2(b), essa alocação fictícia agora é descartada no próximo refresh/navegação (porque a tela volta a buscar os dados reais do backend) — o que na prática só torna mais visível uma limitação que já existia. Corrigir exigiria um endpoint novo de criação de alocação no backend; fora do escopo desta auditoria (correção de erros reais, não de features ausentes). |
| `HelloWorld.vue` e `LoadingIndicator.vue` (+ `stores/ui.ts`) — código morto | Nenhum dos dois componentes é importado em lugar algum do projeto (`HelloWorld.vue` é um placeholder vazio, sobra do scaffold inicial do Vite). `LoadingIndicator.vue` consome `useUiStore().isLoading`, mas a action que alteraria esse estado (`setLoading`) também nunca é chamada por nenhum outro arquivo — ou seja, o "spinner de carregamento global" foi montado (store + componente) mas nunca conectado a nenhuma chamada assíncrona real, e o componente nunca é renderizado em `App.vue`/`DefaultLayout.vue`. Não corrigido (remoção de arquivo não é possível neste ambiente de sandbox, ver §3.2); recomenda-se excluir os 3 artefatos ou efetivamente conectá-los, dependendo se a intenção é ter um spinner global. |
| `tailwindcss` / `@tailwindcss/vite` fixados em `^4.0.0-alpha.17` (`frontend/package.json`) | O projeto já usa a sintaxe definitiva do Tailwind v4 (`@import 'tailwindcss'` + `@theme` em `index.css`), mas a dependência ainda aponta para uma versão **alpha** pré-lançamento, hoje (jun/2026) muito atrás da v4 estável. Funciona, mas é risco de build em ambientes novos (versão alpha pode ser despublicada do npm) e dívida técnica de dependência. Recomenda-se atualizar para a versão estável do Tailwind v4 — não aplicado nesta sessão por não ser possível validar `npm install`/build com a versão nova neste ambiente de sandbox. |
| `tsconfig.node.json` | Verificado e confirmado **correto** (referenciado por `tsconfig.json` via `"references"`, existe, e configura corretamente o typecheck de `vite.config.ts` com `composite: true` e suporte a Node). Mencionado aqui apenas porque foi checado explicitamente a pedido do escopo "qualquer coisa que possa impedir `npm run build`" — sem problema encontrado. |
| Fallback SPA do backend (`src/main.py`, rota `/{full_path:path}`) vs. fallback do Vue Router | Confirmados consistentes: o backend serve `index.html` para qualquer rota que não comece com `api`, e o Vue Router tem `{ path: '/:pathMatch(.*)*', redirect: '/' }` (já adicionado na seção §3.4). Os dois mecanismos não conflitam — o backend decide servir o HTML, e dentro do SPA o router decide o que mostrar. |

### 7.4. Resultado da verificação desta atualização

Todos os arquivos alterados nesta sessão foram relidos integralmente após a edição para confirmar a sintaxe e a lógica (diffs revisados manualmente, já que a execução de `npm run build`/`vue-tsc` neste ambiente de sandbox permanece não confiável — ver §4.2 sobre o problema de `virtiofs`). Nenhuma regressão identificada nos arquivos tocados: `src/models/schemas.py` (n/a nesta seção), `alembic/versions/8a2efbe37bb6_*.py`, `src/resources/database.py`, `.env.example`, `docs/SETUP.md`, `README.md`, `frontend/src/views/Login.vue`, `SaaDashboard.vue`, `SaaGrades.vue`, `SaaSalas.vue`, `SaaAlocacoes.vue`, `SaaHistorico.vue`.

### 7.5. Conclusão atualizada

Com as correções das seções 3 e 7, o backend não tem mais nenhum caminho de crash não tratado conhecido relacionado a configuração ausente (AGHU) ou migração destrutiva, e a documentação de setup reflete as variáveis de ambiente realmente usadas. No frontend, o módulo SAA — o núcleo funcional do sistema — agora carrega corretamente dados reais em qualquer ponto de entrada (login direto, link direto, refresh de página), o que antes só funcionava se o usuário seguisse um caminho de navegação específico. Os itens da seção 7.3 são dívida técnica documentada e conhecida, não bugs ocultos: nenhum impede `npm install`, `npm run dev`/`build` ou a execução local do backend.

---

## 8. Atualização — Paridade de Busca em Grades, Busca Insensível a Acentos e Spinner de Importação

**Data desta atualização:** 17/06/2026 (sessão de continuação, a partir de feedback direto do usuário sobre a tela de Grades de Atendimento, busca por especialidade e importação de CSV).

### 8.1. `SaaGrades.vue` — sem botão de busca, parecia "travada" ao filtrar

A tela de Grades de Atendimento filtra os dados inteiramente no cliente (`computed` sobre `store.grades`, já carregado via `onMounted` desde a correção do §7.2(b)), sem nenhum botão de "Buscar" e sem indicador de carregamento — diferente da tela de Consultas, que tem busca paginada no servidor com botão "Buscar" e spinner explícitos. Reportado pelo usuário como filtros "bugados para carregar".

**Correção aplicada:** adicionado botão "Buscar" (chama `buscar()`, que reexecuta `buscarGrades`/`buscarSalas`/`buscarAlocacoes`/`buscarConflitos` em paralelo) e um spinner (`animate-spin`) exibido enquanto `store.carregando` é verdadeiro, ocultando a tabela nesse intervalo — mesmo padrão visual já usado em `SaaConsultas.vue`. Isso dá ao usuário uma confirmação visível de que os dados estão sendo (re)carregados e uma forma manual de atualizar a tela após uma nova importação, sem precisar dar F5.

### 8.2. Busca por especialidade sensível a maiúsculas/acentos — em Consultas e Grades

Em ambas as telas, buscar `"obstetricia"` (sem acento, minúsculo) não encontrava `"Obstetrícia"` nos dados. Em Consultas a comparação usava apenas `.upper()` no backend (`consulta_aghu_csv_provider.py`); em Grades a comparação era feita com `.includes()` puro no frontend, sem nenhuma normalização.

**Correção aplicada:**
- Backend (`src/providers/implementations/consulta_aghu_csv_provider.py`): nova função `_normalizar_busca()` usando `unicodedata.normalize("NFKD", ...)` + remoção dos caracteres combinantes (acentos) + `.upper()`. Aplicada nos dois lados de cada comparação (termo buscado e valor do CSV) para `especialidade`, `unidade_funcional`, `profissional`, `turno`, `dia_semana` e `situacao_consulta` em `listar_consultas()`.
- Frontend (novo arquivo `frontend/src/utils/texto.ts`): helpers `normalizarBusca()`/`contemSemAcento()`, mesma estratégia (NFD + remoção de marcas combinantes U+0300–U+036F + `toLowerCase()`). Usado em `SaaGrades.vue` no filtro de especialidade.

Resultado: `"cardiologia"`, `"CARDIOLOGIA"` e `"Cardiología"` agora retornam o mesmo resultado em ambas as telas, com ou sem acento, em qualquer combinação de caixa.

### 8.3. Importação de CSV sem indicação visual de progresso

Em `SaaImportar.vue`/`ImportCard.vue`, ao enviar um CSV o card ficava parado — sem nenhum feedback — até a resposta do servidor chegar, dando a impressão de que o upload havia travado. O aviso de resultado (sucesso/erro) só aparecia ao final, como já era esperado e foi mantido sem alterações.

**Correção aplicada:** novo estado `carregando` (objeto `reactive` por tipo de importação — grades/consultas/salas/restrições/alocações) em `SaaImportar.vue`, ligado/desligado em um bloco `try/finally` ao redor de cada `importar()`, e passado como prop para `ImportCard.vue`. Enquanto `carregando` é verdadeiro, o card mostra um spinner (`animate-spin`) com a mensagem "Processando `<arquivo>`…" e desabilita clique/drag-and-drop/input de arquivo, evitando reenvios duplicados durante o processamento. O aviso de resultado existente não foi alterado — continua aparecendo normalmente após o spinner desaparecer.

### 8.4. Verificação

Todos os arquivos alterados (`SaaGrades.vue`, `frontend/src/utils/texto.ts`, `consulta_aghu_csv_provider.py`, `ImportCard.vue`, `SaaImportar.vue`) foram relidos integralmente após as edições para confirmar sintaxe e lógica completas. A lógica de `_normalizar_busca`/`normalizarBusca` foi validada de forma independente (reimplementação equivalente em Python e Node, fora do arquivo do projeto), confirmando que `"Obstetrícia"` e `"obstetricia"` passam a ser tratadas como equivalentes em ambos os lados (backend e frontend), e que a busca antiga (`.upper()` puro / `.includes()` puro) falharia nesse mesmo caso — confirmando que o bug era real e que a correção o resolve. Nenhuma regressão identificada nos arquivos tocados.

---

## 9. Atualização — Colunas Opcionais de Salas e Importação Tolerante a Valores Vazios

**Data desta atualização:** 17/06/2026 (sessão de continuação, a partir de um print de erro do usuário ao importar `salas.csv`).

### 9.1. `sala_csv_provider.py` — colunas opcionais sendo exigidas como obrigatórias

A tela de importação informa: *"Colunas obrigatórias: id, numero, bloco, status. Opcionais: andar, acessibilidade, equipamentos (separados por ;), especialidade_preferencial"*. O código, porém, definia:

```python
COLUNAS_OBRIGATORIAS = {"id", "numero", "bloco", "andar", "status", "acessibilidade", "equipamentos"}
```

ou seja, `andar`, `acessibilidade` e `equipamentos` também eram exigidas, contradizendo a própria UI — um `salas.csv` válido (só com as 4 colunas realmente obrigatórias) era rejeitado com `'salas.csv' está faltando colunas obrigatórias: [...]`.

**Causa adicional identificada:** `_ler_csv()` lia o arquivo sempre com separador `,` fixo e sem detectar BOM. Um CSV exportado do Excel em pt-BR (separador `;`, comum nesse locale) era lido como **uma única coluna gigante** — fazendo com que `set(linhas[0].keys())` tivesse só 1 elemento e **todas** as colunas esperadas (as 4 obrigatórias e as 3 opcionais, exatamente os 7 nomes do print do usuário) aparecessem como "ausentes" simultaneamente. Esse padrão de detecção de separador/encoding já existia nos providers AGHU (`grade_aghu_csv_provider.py`, `consulta_aghu_csv_provider.py`), mas não tinha sido replicado nos providers legados do SAA (`sala_csv_provider.py`, `restricao_csv_provider.py`, `alocacao_saa_csv_provider.py`).

**Correção aplicada:**
- `COLUNAS_OBRIGATORIAS` reduzida para `{"id", "numero", "bloco", "status"}` — única e exatamente o que a UI promete.
- `_ler_csv()` agora detecta separador (`,` ou `;`) e encoding (`utf-8-sig`/`utf-8`/`latin-1`) automaticamente, igual aos providers AGHU.
- Leitura de cada linha passou a usar `.get()` em vez de `linha["coluna"]` para os campos opcionais (`andar`, `acessibilidade`, `equipamentos`, `especialidade_preferencial`), evitando `KeyError` quando a coluna simplesmente não existe no arquivo.

### 9.2. Importação tolerante a células vazias (salas, restrições e alocações)

Pedido explícito do usuário: nenhum dos CSVs (salas, restrições, alocações) deveria tratar uma célula/valor em branco como erro. Investigando os três providers, encontrado um risco real de crash não tratado: quando uma linha tem **menos colunas do que o cabeçalho** (células finais omitidas, sem vírgula sobrando — comum em edição manual de CSV), `csv.DictReader` preenche os campos faltantes com `None` (não `""`). O código então fazia `linha["campo"].strip()`, e `None.strip()` lança `AttributeError` — uma exceção **não capturada** pelos blocos `except (ValueError, KeyError)` existentes, resultando em erro 500 genérico em vez de uma importação tolerante.

**Correção aplicada** em `sala_csv_provider.py`, `restricao_csv_provider.py` e `alocacao_saa_csv_provider.py`:
- `_ler_csv()` agora normaliza todo valor ausente/`None` para `""` no momento da leitura (`{k: (v.strip() if v else "") for k, v in row.items()}`), igual ao padrão já usado nos providers AGHU.
- Todo acesso a campo de linha trocado de `linha["x"]` para `linha.get("x", "")`, eliminando o risco de `KeyError`/`AttributeError` por célula ou coluna ausente.
- `alocacao_saa_csv_provider.py` recebeu a mesma detecção de separador/encoding dos demais, por consistência (nenhuma coluna opcional ali — todas as 5 continuam exigidas, conforme já informado na UI — apenas a tolerância a valores em branco foi adicionada).

### 9.3. Verificação

Os três arquivos editados foram relidos integralmente após a edição (sintaxe e lógica confirmadas). A lógica de leitura/normalização foi validada com uma reimplementação equivalente em um script Python isolado, cobrindo 4 cenários: (1) CSV de salas só com as colunas obrigatórias — passa; (2) CSV de salas com separador `;` e todas as colunas — passa (antes ficaria com 1 coluna só e falharia com as 7 colunas "ausentes", reproduzindo exatamente o erro do print do usuário); (3) linha com células finais omitidas — não gera mais exceção, valores ausentes tornam-se `""`; (4) CSV realmente faltando uma coluna obrigatória (`status`) — continua sendo rejeitado corretamente, confirmando que a validação de colunas genuinamente obrigatórias não foi enfraquecida.

---

## 10. Atualização — Causa Raiz do Travamento/Crash Após Importação ("o saa esta travando muito, ele crachou depois de colocar os arquivos")

**Data desta atualização:** 17/06/2026 (sessão de continuação, a partir de relato direto do usuário de que a aplicação travava muito e chegou a "crachar" depois de subir arquivos).

### 10.1. Causa raiz: `data/vw_consultas_2026.csv` corrompido com bytes nulos (0x00)

Investigação revelou que `data/vw_consultas_2026.csv` estava com **107.497.577 bytes** em disco, mas continha apenas **789 linhas reais de dados nos primeiros 202.564 bytes** — todo o restante do arquivo (mais de 107 MB) era um único bloco contínuo de bytes nulos (`0x00`), provavelmente resultado de uma gravação/cópia interrompida durante uma importação anterior.

Bytes nulos são caracteres Unicode válidos e passam silenciosamente por `Path.read_text()` e pela correção de mojibake já existente no provider — o problema só se manifestava na etapa final de parsing, onde `csv.DictReader` lançava `_csv.Error: line contains NUL`. Essa exceção **não é uma subclasse de `ValueError`/`KeyError`**, então não era capturada por nenhum dos blocos `except` já existentes no projeto (nem no provider, nem nos routers `aghu.py`/`importacao.py`) — o erro subia cru, derrubando a requisição.

Agravante de performance: `ConsultaAghuCsvProvider._carregar()` só grava `self._cache` **após** um parse bem-sucedido. Como o parse falhava sempre, **toda requisição relacionada a consultas refazia a leitura e o processamento completo dos 107 MB do zero**, sem nenhum benefício de cache — explicando o relato de "travando muito" (cada chamada a qualquer endpoint de consultas/capacidade/qualidade-dados era uma operação pesada e fadada a falhar) e o crash sob uso repetido (ex.: dashboard chamando vários endpoints AGHU em sequência).

### 10.2. Correção imediata: restauração do arquivo

`data/importados/` (backups automáticos feitos antes de cada importação) continha duas cópias de 202.564 bytes — exatamente o tamanho do trecho de dados válidos identificado no arquivo corrompido. Verificada a integridade de uma delas (sem bytes nulos, 788 linhas de dados, parse limpo) e usada para restaurar `data/vw_consultas_2026.csv`.

### 10.3. Correção estrutural: proteção contra corrupção por bytes nulos em todos os providers de CSV

Para que esse cenário não derrube a aplicação novamente — com qualquer arquivo, não só `vw_consultas_2026.csv` — foi aplicado o mesmo padrão de defesa em **todos** os providers de CSV do projeto:

- `consulta_aghu_csv_provider.py`
- `grade_aghu_csv_provider.py`
- `sala_csv_provider.py`
- `restricao_csv_provider.py`
- `alocacao_saa_csv_provider.py` (checagem posicionada **depois** do retorno antecipado para arquivo vazio, já que arquivo de alocações sem linhas de dados é um estado legítimo)

Em cada um: (1) checagem explícita de `"\x00" in texto` logo após a leitura do arquivo, levantando `ValueError` com mensagem clara em português orientando o usuário a reexportar/regerar o arquivo; (2) o laço de `csv.DictReader` passou a estar dentro de um `try/except csv.Error`, convertendo qualquer erro estrutural remanescente do parser CSV (não só bytes nulos) em `ValueError` — exceção já tratada pelos routers existentes (`except (FileNotFoundError, ValueError)` em `importacao.py`; `except ValueError` em `aghu.py`), resultando em uma resposta HTTP 422 com mensagem amigável em vez de um 500 não tratado.

Esse fix também resolve o problema de cache: como a validação agora falha rápido (antes do parse pesado) e de forma previsível, um arquivo corrompido nunca chega a ser publicado como o arquivo ativo (a validação em `_publicar_upload_validado()` já rejeita o upload antes de sobrescrever o arquivo em uso).

### 10.4. Verificação

Os cinco providers editados foram relidos integralmente para confirmar que cada inserção manteve a sintaxe e a indentação corretas (com atenção especial a `alocacao_saa_csv_provider.py`, cuja checagem precisa vir depois do `if not texto.strip(): return []` para preservar o comportamento de "arquivo vazio é válido"). A restauração de `vw_consultas_2026.csv` foi confirmada programaticamente (ausência de bytes nulos, 788 linhas, parse limpo via `csv.reader`) antes de substituir o arquivo corrompido.

**Ação pendente do usuário:** como o backend roda em um container Docker cuja imagem é construída via `COPY . .` (sem bind mount de `src/` para o container — ver `Dockerfile`/`docker-compose.yml`), essas correções de código só terão efeito após reconstruir a imagem com `docker compose up -d --build` (um `docker compose up -d` simples reaproveita a imagem antiga e não aplica as mudanças).

### 10.5. Correção estrutural adicional: `importacao.py` publicava salas/restrições/alocações antes de validar

Investigação de acompanhamento ("e se eu subir um novo arquivo corrompido, o que acontece?") revelou que, diferente dos endpoints de grades e consultas, os endpoints de **salas, restrições e alocações** em `src/routers/importacao.py` escreviam o upload diretamente sobre o arquivo ativo (`data/salas.csv`, `data/restricoes.csv`, `data/alocacoes.csv`) **antes** de validar o conteúdo — um upload corrompido sobrescrevia o arquivo em uso mesmo quando a validação subsequente falhava, deixando o sistema sem dados de salas/restrições/alocações até uma nova importação válida.

Corrigido estendendo a todos os 5 endpoints o mesmo padrão já usado em grades/consultas: `_salvar_upload_temporario()` (grava em arquivo temporário) → validação do provider contra o caminho temporário → `_publicar_upload_validado()` (backup do arquivo atual + `Path.replace()` atômico) só em caso de sucesso, ou `_remover_temporario()` em caso de falha. Como efeito colateral dessa reescrita, o helper `_contar_linhas_csv()` (que relia em uma leitura própria, sem proteção contra bytes nulos, do arquivo recém-enviado) foi removido — `linhas_lidas` agora vem diretamente da contagem já validada pelo provider (`len(salas)`, `len(restricoes)`, ou do novo atributo `provider.ultimo_linhas_lidas` para alocações), eliminando um segundo ponto onde o mesmo `_csv.Error: line contains NUL` do §10.1 poderia ocorrer sem proteção.

---

## 11. Atualização — Recuperação Automática de Bloco Final de Bytes Nulos

**Data desta atualização:** 17/06/2026 (mesma sessão de continuação, a partir da pergunta do usuário: "mas tem como tratar essa parte vazia?").

### 11.1. Problema com a correção do §10.3

A correção anterior rejeita **qualquer** arquivo com bytes nulos, mesmo no caso real observado (§10.1): um grande bloco de bytes nulos colado ao final do arquivo, após os dados válidos. Rejeitar esse caso obriga o usuário a editar/truncar o arquivo manualmente antes de reenviar, quando na prática os dados válidos no início do arquivo são perfeitamente recuperáveis.

### 11.2. Recuperação automática quando seguro, rejeição quando ambíguo

Adicionado o helper `_tratar_bytes_nulos()` (duplicado nos 5 providers, seguindo a convenção já existente no projeto de não compartilhar helpers entre eles) com uma regra simples: a partir do primeiro byte nulo, se o restante do arquivo for **só** bytes nulos (mais espaços/quebras de linha) — ou seja, um bloco final puro — e houver conteúdo real antes dele, o trecho final é descartado automaticamente e a importação prossegue normalmente com um aviso explicando o que foi removido. Se os bytes nulos estiverem espalhados/misturados com dados reais, ou não houver nenhum conteúdo recuperável antes deles, o arquivo continua sendo rejeitado com `ValueError` — não é seguro adivinhar o que é dado real e o que é corrupção nesses casos.

O aviso é propagado até a resposta da API por providers que expõem o estado da última leitura via atributos de instância (`ultimo_aviso`, `ultimo_aviso_corrupcao`, conforme o provider) — escolha feita para não alterar a assinatura de nenhum método público já usado por outros 9 pontos de chamada no projeto (controllers/routers).

### 11.3. Autocura: a correção é gravada de volta no arquivo

Truncar apenas o texto em memória não seria suficiente: o arquivo no disco continuaria contendo o bloco de bytes nulos para sempre, e cada leitura futura repetiria o mesmo truncamento sem nunca limpar a causa raiz (o mesmo desperdício de reprocessamento identificado no §10.1). Por isso, ao detectar e truncar um bloco final de bytes nulos, os 5 providers gravam a versão limpa de volta no arquivo (`caminho.write_text(...)`) — no fluxo de importação isso acontece no arquivo temporário, antes mesmo dele se tornar o arquivo ativo; numa leitura direta do arquivo já em uso, o arquivo ativo é limpo imediatamente.

**Bug encontrado e corrigido durante a verificação:** a função de detecção de encoding (`_detectar_encoding`) tenta `"utf-8-sig"` antes de `"utf-8"`, e `read_text(encoding="utf-8-sig")` decodifica com sucesso tanto arquivos com BOM quanto sem BOM — então praticamente todo arquivo UTF-8 é classificado como `"utf-8-sig"`, com ou sem BOM real. Gravar de volta usando esse mesmo encoding (`write_text(encoding="utf-8-sig")`) **sempre adiciona um BOM novo**, mesmo em arquivos que nunca tiveram um — confirmado por simulação isolada antes de aplicar a correção. Os 5 pontos de autocura agora gravam sempre como `"utf-8"` puro quando o encoding detectado for `"utf-8-sig"` (o texto em memória já não contém o BOM, pois o decode `utf-8-sig` o remove), evitando introduzir esse artefato espúrio no arquivo limpo.

### 11.4. Verificação

Simulação isolada (fora do mount do projeto, por conta da instabilidade já registrada no §10.4 para verificação durante esta sessão) reproduzindo a lógica exata dos providers, cobrindo: (a) bloco final puro de bytes nulos com dados válidos antes — truncado, autocurado em disco sem BOM espúrio, e importado com aviso; (b) bytes nulos espalhados/misturados com dados — rejeitado com `ValueError`; (c) arquivo 100% bytes nulos (sem prefixo recuperável) — rejeitado; (d) arquivo só com cabeçalho antes do bloco nulo — autocurado em disco (cabeçalho preservado, bloco nulo removido) e em seguida rejeitado como "vazio" por não ter linhas de dados, efeito colateral aceitável já que o arquivo gigante corrompido fica permanentemente reduzido ao cabeçalho; (e) fluxo ponta a ponta via a classe do provider, confirmando que o aviso fica disponível no atributo de instância lido pelo router. Os 5 arquivos de provider foram relidos integralmente após as edições, incluindo a correção de um bug de retorno de tupla (`grade_aghu_csv_provider.py` ainda retornava 2 valores após a assinatura ter sido alterada para 3) encontrado e corrigido antes desta verificação.

## 12. Atualização — Endpoints de Reset de Dados

**Data desta atualização:** 17/06/2026 (mesma sessão de continuação, a partir do pedido do usuário: "quero que crie", em resposta à explicação de como os dados são armazenados no backend e à pergunta sobre como limpar/recarregar).

### 12.1. Objetivo

Permitir limpar os dados atuais de qualquer um dos 5 datasets baseados em CSV (grades, consultas, salas, restrições, alocações) sem precisar editar arquivos manualmente, preservando uma cópia de segurança do conteúdo anterior e, no caso de alocações, também zerando os ajustes manuais persistidos em SQLite.

### 12.2. Contrato do endpoint

```
POST /api/importacao/reset/{tipo}
```

`tipo` é restrito por `Literal["grades", "consultas", "salas", "restricoes", "alocacoes"]` (validação automática do FastAPI — um `tipo` fora dessa lista retorna 422 antes mesmo de chegar à função). Resposta no schema `ResetResultado` (`tipo`, `arquivo`, `linhas_removidas`, `backup`, `mensagem`).

Comportamento:

- Arquivo inexistente → retorna `linhas_removidas=0`, `backup=None`, mensagem informando que não havia nada para limpar. Nenhum arquivo é criado do zero.
- Arquivo existente → conta as linhas de dados atuais de forma **tolerante a erro** (qualquer exceção do provider correspondente, inclusive em arquivo corrompido, é capturada e tratada como 0 — o reset nunca deve ser bloqueado pela própria corrupção que talvez esteja sendo usado para resolver); extrai o cabeçalho real lendo só a primeira linha do arquivo atual (tentando `utf-8-sig` → `utf-8` → `latin-1`, cortando em `\x00` se houver) em vez de hardcodear um cabeçalho "canônico" por tipo — preserva colunas extras ou customizadas que o arquivo em uso já tinha; faz backup do conteúdo anterior reaproveitando `_fazer_backup_se_existir()` (mesmo padrão timestampado de `data/importados/{stem}.{YYYYMMDDHHMMSS}{suffix}` usado pelos endpoints de importação); regrava o arquivo só com a linha de cabeçalho, sempre com `encoding="utf-8"` (nunca `"utf-8-sig"`, para não reintroduzir o bug de BOM espúrio corrigido no §11.3).
- Quando `tipo == "alocacoes"`, chama `AlocacaoSaaCsvProvider.limpar_ajustes()` (novo método, `DELETE FROM alocacoes_ajustes`) depois de regravar o CSV — necessário porque um ajuste manual antigo sobrescreveria silenciosamente um dado novo importado com o mesmo `id`. A tabela `historico_ajustes` é deliberadamente preservada (decisão de design já tomada antes desta implementação): é um registro de auditoria independente do estado atual dos dados, não deve ser apagado por um reset.

Para identificar qual arquivo `_fazer_backup_se_existir()` acabou de criar (a função não retorna o caminho), o endpoint compara o conteúdo de `data/importados/` antes e depois da chamada e usa a diferença.

### 12.3. Arquivos alterados

- `src/models/schemas.py` — schema `ResetResultado` adicionado.
- `src/providers/implementations/alocacao_saa_csv_provider.py` — método `limpar_ajustes()` adicionado.
- `src/providers/implementations/grade_aghu_csv_provider.py`, `consulta_aghu_csv_provider.py`, `sala_csv_provider.py`, `restricao_csv_provider.py` — relaxados para tratar "cabeçalho presente, 0 linhas de dados" como estado válido (já era o comportamento de `alocacao_saa_csv_provider.py`), pré-requisito para que o reset não deixe o dataset "vazio mas com erro" (HTTP 422) até a próxima importação.
- `src/routers/importacao.py` — novo endpoint `resetar_dados` (`POST /reset/{tipo}`) e helpers `_TIPOS_RESET`, `TipoReset`, `_ler_cabecalho`, `_contar_linhas_atuais`. Os 5 endpoints de importação pré-existentes não foram alterados.

### 12.4. Verificação

Mesma limitação de mount já registrada no §10.4/§11.4 esteve presente nesta sessão (de forma ainda mais inconsistente: comparando os 6 arquivos tocados nesta feature, alguns apareceram atualizados via bash e outros continuaram mostrando conteúdo antigo por tempo indeterminado, sem padrão claro — nem todos os arquivos da mesma idade de edição se comportaram igual). Por isso, a verificação não usou o mount do bash sobre os arquivos reais do projeto; usou:

1. **Releitura via ferramenta Read** (fonte de verdade, não passa pelo mount) de `src/routers/importacao.py` e `alocacao_saa_csv_provider.py` integralmente após as edições, confirmando que o código final está sintaticamente correto e corresponde exatamente ao design.
2. **Simulação comportamental isolada** (`/tmp/simreset/`, fora do mount): reconstrução fiel dos 5 providers e do endpoint de reset, com dados de teste (3 grades, 2 salas, 1 restrição, 2 alocações, 2 consultas, mais 1 ajuste manual seedado no SQLite). Resultados:
   - Reset de cada um dos 5 tipos retornou `linhas_removidas` correto (3, 2, 1, 2, 2) e um caminho de backup válido em `data/importados/`.
   - Reset de alocações reportou corretamente a remoção de 1 ajuste manual.
   - Após o reset, todos os 5 métodos de listagem retornaram `[]` sem erro (confirma que a folga "0 linhas é válido" do §12.3 integra corretamente com o reset).
   - `listar_alocacoes()` (visão mesclada CSV+SQLite) retornou `[]`; consulta direta ao SQLite confirmou a tabela `alocacoes_ajustes` vazia.
   - Bytes finais de cada um dos 5 arquivos resetados continham exatamente `<cabeçalho>\n`, sem BOM.
   - Arquivos de backup criados em `data/importados/` com o nome timestampado esperado.
3. **Não foi possível rodar a suíte `pytest` real** contra o estado atual do projeto nesta sessão, pela mesma razão de instabilidade do mount. Como mitigação, análise de risco: todas as mudanças desta feature são estritamente aditivas — um método novo (`limpar_ajustes`), um endpoint novo (`/reset/{tipo}`) e suas funções auxiliares — nenhuma assinatura ou comportamento de código já existente (e já coberto pelos 107 testes mencionados no §10) foi alterada, com exceção da relaxação "0 linhas válido" do item 12.3, que já havia sido confirmada compatível com a suíte de testes antes desta sessão (ver item 6 do `docs/STATUS_ATUAL.md`). **Recomendação explícita ao usuário**: rodar `pytest` localmente (fora deste ambiente) antes de considerar a feature validada em produção.

### 12.5. Deploy

Como o container é construído com `COPY . .` (ver auditoria de infraestrutura, seção 2), as mudanças só entram em produção após `docker compose up -d --build`.

---

## 13. Atualização — Alocação Não Aparecia no Painel + Unicidade de Grades

**Data desta atualização:** 17/06/2026 (mesma sessão de continuação, a partir do pedido do usuário: *"analise o projeto, pois quando aloco uma sala na pagina de grades, no painel nao aparece. alem disso, grades nao podem se repetir. crie um botao no saa em que ele remove as grades repetidas, pois elas devem ser unicas."*).

### 13.1. Causa raiz #1 — alocação criada na tela de Grades não aparecia no Painel SAA

`frontend/src/components/EditarAlocacao.vue` (`salvar()`) fazia `store.alocacoes.push({...})` localmente quando a grade ainda não tinha sala — nunca chamava o backend. O Painel SAA recarrega `GET /api/alocacoes` ao montar, então essa alocação "fantasma" desaparecia. Mais grave: **não existia endpoint de criação** de alocação no backend, apenas `POST /api/alocacoes/ajustar` (exige alocação pré-existente).

### 13.2. Causa raiz #2 — grades duplicadas

`vw_grades.csv` (export real do AGHU) tem uma linha por `Condicao_De_Atendimento` (RETORNO, CONSULTA PRIMEIRA VEZ, INTERCONSULTA etc.) para a mesma grade/dia/turno — dado real e legítimo, mas redundante para o SAA, que só precisa saber qual sala está alocada em cada horário. Esse mesmo CSV alimenta também o módulo "AGHU: Dados Reais" (`/api/aghu/*`, `capacidade_service`, `qualidade_dados_service`), que precisa de **todas** as linhas (cada uma tem `Quantidade_Vagas` própria). Por isso a deduplicação não pode tocar no arquivo físico — só pode existir na camada de adaptação exclusiva do SAA.

**Critério de unicidade definido:** `(grade_id, dia_semana, turno)`. Um `grade_id` recorrente em dias/turnos diferentes é uma grade legítima, não uma duplicata.

### 13.3. Correções e funcionalidades implementadas

**Backend:**
- `GradeAghuDashboardProvider.listar_grades()`/`buscar_grade()` — deduplicam por `(grade_id, dia_semana, turno)`, mantendo a primeira ocorrência; nunca escrevem em `vw_grades.csv`.
- `GradeAghuDashboardProvider.relatorio_duplicadas() -> tuple[int, int]` — novo método, calcula `(total_linhas_brutas, total_grades_unicas)`.
- `POST /api/grades/remover-duplicadas` (novo, `src/routers/grade.py`) — expõe o relatório acima via schema `RemocaoGradesDuplicadasResultado`; faz `isinstance(provider, GradeAghuDashboardProvider)` e responde 501 para outros providers (a interface `GradeProviderInterface` só exige `listar_grades`/`buscar_grade`, então estender a interface não era necessário).
- `POST /api/alocacoes` (novo, `criar_alocacao` em `src/controllers/alocacao_controller.py` e `src/routers/alocacao.py`) — cria a primeira alocação de uma grade. Busca a grade pela tripla `(id, dia_semana, turno)` (não só `grade_id`, ambíguo em grades recorrentes), valida a sala, bloqueia criar uma 2ª alocação para a mesma ocorrência (orienta a usar `/ajustar`), simula conflitos via `calcular_conflitos()`, exige justificativa se houver conflito crítico/operacional, persiste e grava histórico (`sala_anterior_id=""`).
- **Bug corrigido em `AlocacaoSaaCsvProvider.listar_alocacoes()`**: a função só percorria o CSV base substituindo por ajustes do SQLite via `id` — alocações que existem **somente** no SQLite (as criadas pelo novo endpoint) eram descartadas silenciosamente. Corrigido para também incluir essas entradas (rastreadas em um set `ids_base`).
- Schemas novos em `src/models/schemas.py`: `RemocaoGradesDuplicadasResultado`, `CriarAlocacaoRequest`, `CriarAlocacaoResponse`.
- **Bug adicional encontrado e corrigido em `src/services/conflito_service.py` (regra C07 — "grade sem sala associada")**: usava só `grade_id` para decidir se uma grade tinha alocação. Com grades recorrentes (mesmo `grade_id`, dias/turnos diferentes), uma ocorrência alocada mascarava a falta de sala de outra ocorrência do mesmo `grade_id` — falso negativo no Painel SAA. Corrigido para usar a tripla `(grade_id, dia_semana, turno)`, igual ao restante da correção. `grade_map` (usado só por C08/C09/C10, que leem `especialidade`, invariante entre ocorrências) foi deixado como estava — sem risco de correção ali.

**Frontend:**
- `frontend/src/stores/saa.ts` — `getAlocacaoPorGrade(gradeId, diaSemana?, turno?)` agora aceita a chave composta opcional; novas actions `criarAlocacao()` (chama `POST /api/alocacoes` de fato) e `removerGradesDuplicadas()` (chama o endpoint de verificação).
- `frontend/src/components/EditarAlocacao.vue` — `salvar()` chama `store.criarAlocacao()` quando não há alocação prévia, em vez do push local; `alocacaoAtual` usa a chave composta. Esta é a correção direta do bug relatado (§13.1).
- `frontend/src/views/SaaDashboard.vue` — `alocacaoDaGrade()` recebe a `Grade` inteira e usa um `Map` indexado por `grade_id|dia_semana|turno`, não mais só `grade_id`.
- `frontend/src/views/SaaGrades.vue` — as duas chamadas a `getAlocacaoPorGrade()` passam `dia_semana`/`turno`; novo botão **"Verificar grades duplicadas"** no cabeçalho, que chama `removerGradesDuplicadas()` e mostra o resultado via toast (sucesso se havia duplicatas normalizadas, info se já estava único, erro em falha).

### 13.4. Por que o botão verifica em vez de excluir

A deduplicação já é automática em toda listagem do SAA — não há duplicatas "soltas" para apagar nesse nível, e apagar linhas de `vw_grades.csv` quebraria os relatórios de capacidade/qualidade do módulo AGHU (§13.2). O botão foi desenhado como uma ação de **verificação/confirmação não destrutiva**: comunica ao usuário que a unicidade está garantida e quantas linhas brutas colapsaram em quantas grades únicas, sem efeito colateral nos outros módulos.

### 13.5. Verificação

Mesma limitação de mount já registrada nos §10.4/§11.4/§12.4: `stat`/`wc -l` via bash mostraram conteúdo com mais de 24h de defasagem mesmo imediatamente após edições nesta sessão (ex.: `conflito_service.py` reportado com a contagem de linhas pré-correção). Verificação feita via:

1. **Releitura integral via ferramenta Read** (não passa pelo mount) de todos os 11 arquivos alterados (listados no `docs/STATUS_ATUAL.md`), confirmando sintaxe, assinaturas, e consistência de tipos entre request/response do backend e os tipos TypeScript do frontend.
2. **Revisão de compatibilidade com a suíte de testes existente**: `tests/test_saa_routers.py` (374 linhas, lido por completo — `FakeGradeProvider` não implementa `relatorio_duplicadas()`, o que é inócuo porque o endpoint novo type-checka e retorna 501 para providers que não sejam `GradeAghuDashboardProvider`; nenhum teste existente cobre `POST /api/alocacoes` nem o endpoint de duplicatas, então nada conflita), `tests/test_alocacao_saa_csv_provider.py` (36 linhas, lido por completo — o fix do merge CSV+SQLite não afeta o teste existente), e os fixtures default de `tests/test_conflito_service.py` (`dia_semana="Segunda"`, `turno="Manhã"` tanto em `_grade()` quanto em `_aloc()`, confirmando que o fix de C07 é compatível com `test_grade_sem_alocacao_gera_conflito_critico` e `test_grade_com_alocacao_nao_gera_grade_sem_sala`).
3. **Não foi possível rodar a suíte `pytest` real** nesta sessão, pela mesma instabilidade de mount das seções anteriores. **Recomendação explícita ao usuário**: rodar `pytest` localmente e testar manualmente o fluxo (importar grade real → alocar sala em "Grades de Atendimento" → confirmar que aparece no Painel SAA) antes de considerar a feature validada em produção.

### 13.6. Deploy

Mesma observação do §12.5 — mudanças só entram em produção após rebuild do container (`docker compose up -d --build`), já que o `Dockerfile` usa `COPY . .`.
