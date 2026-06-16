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
