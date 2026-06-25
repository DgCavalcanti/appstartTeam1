# Prompt para Claude: implementar alocacao automatica no SAA

Voce esta trabalhando no projeto SAA (Sistema de Apoio a Alocacao Ambulatorial), uma aplicacao FastAPI + Vue 3. O objetivo e implementar a alocacao automatica de salas usando o motor ja existente em `src/services/alocacao_engine.py`, integrando-o ao backend, aos testes e ao frontend sem quebrar o fluxo atual de importacao por CSV.

## Contexto atual do projeto

- Backend: FastAPI em `src/main.py`.
- Frontend: Vue 3 + Pinia em `frontend/src`.
- Grades reais do AGHU sao importadas por upload em `POST /api/importacao/aghu/grades` e lidas de `data/vw_grades.csv`.
- Consultas reais do AGHU sao importadas por upload em `POST /api/importacao/aghu/consultas` e lidas de `data/vw_consultas_2026.csv`.
- Salas, restricoes e alocacoes tambem sao dados locais persistidos em CSV/SQLite.
- A rota SAA de grades (`GET /api/grades`) ja usa `GradeAghuDashboardProvider`, ou seja, adapta a grade real do AGHU para o modelo interno `Grade`.
- As alocacoes atuais sao gerenciadas por `src/providers/implementations/alocacao_saa_csv_provider.py`, que le `data/alocacoes.csv` e sobrepoe/cria registros persistidos em SQLite (`data/saa.db`, tabela `alocacoes_ajustes`).
- O motor puro de alocacao ja existe em `src/services/alocacao_engine.py`, mas ainda nao esta exposto por endpoint.
- O motor ja normaliza textos para comparacoes robustas com dados reais: `Manhã` casa com `manha`, e especialidades como `ORTOPEDIA (AMBULATÓRIO)` acionam as regras de ortopedia. Nao reimplemente essa normalizacao em outro lugar; reutilize o motor.
- Hoje `tests/test_saa_routers.py` ainda espera que `POST /api/alocacoes/automatica` nao exista. Esse teste deve ser atualizado quando o endpoint for implementado.

## Arquivos principais

Leia estes arquivos antes de alterar codigo:

- `src/services/alocacao_engine.py`
- `src/controllers/alocacao_controller.py`
- `src/routers/alocacao.py`
- `src/providers/implementations/alocacao_saa_csv_provider.py`
- `src/providers/implementations/grade_aghu_dashboard_provider.py`
- `src/services/conflito_service.py`
- `src/models/schemas.py`
- `frontend/src/stores/saa.ts`
- `frontend/src/views/SaaAlocacoes.vue`
- `frontend/src/views/SaaDashboard.vue`
- `tests/test_saa_routers.py`

## Requisito funcional

Implementar uma acao de alocacao automatica que:

1. Receba `dia_semana` e `turno`.
2. Leia as grades do dia/turno, as salas, as restricoes e o historico/alocacoes existentes.
3. Use `src/services/alocacao_engine.py::alocar(...)` para escolher salas.
4. Persista as alocacoes geradas usando o provider atual de alocacoes.
5. Retorne um resumo claro para o frontend: total de grades consideradas, total alocado, total nao alocado, alocacoes criadas/atualizadas, conflitos finais e detalhes das grades sem sala.
6. Atualize a tela do frontend para permitir o disparo da alocacao automatica por dia/turno e recarregar dashboard, alocacoes e conflitos depois da execucao.

## Regra critica: idempotencia

Nao permita que rodar a alocacao automatica duas vezes para o mesmo dia/turno crie duplicatas.

A chave operacional de uma ocorrencia de grade e:

```text
(grade_id, dia_semana, turno)
```

O mesmo `grade_id` pode aparecer em mais de um dia/turno. Portanto, nunca use apenas `grade_id` como identidade da ocorrencia.

Ao persistir uma alocacao automatica:

- Se ja existir alocacao para `(grade_id, dia_semana, turno)`, atualize essa alocacao existente.
- Se nao existir, crie nova `Alocacao`.
- Use IDs deterministas para alocacao automatica, por exemplo:

```text
AUTO-{grade_id}-{dia_normalizado}-{turno_normalizado}-{indice_sala}
```

Se o motor retornar mais de uma sala para a mesma grade, crie uma alocacao por sala. Se o modelo atual nao suportar multiplas salas por grade de forma limpa, documente a limitacao e preserve no minimo o comportamento atual (`qtd_salas_necessarias = 1` no AGHU MVP).

## Regras de seguranca operacional

- Nao sobrescreva alocacoes manuais sem criterio. Sugestao:
  - Parametro `sobrescrever: bool = false`.
  - Se `sobrescrever=false`, pule ocorrencias que ja tenham alocacao.
  - Se `sobrescrever=true`, atualize as alocacoes existentes do dia/turno.
- Nao use banco externo. O projeto esta em modo CSV/SQLite local.
- Nao altere o formato dos CSVs importados do AGHU.
- Nao faça caching dos dados importados; os providers devem continuar lendo os arquivos atuais.
- Toda execucao deve ser reversivel/visivel via historico quando alterar sala existente.

## Contrato sugerido de API

Adicionar em `src/models/schemas.py`:

```python
class AlocacaoAutomaticaRequest(BaseModel):
    dia_semana: str
    turno: str
    sobrescrever: bool = False


class AlocacaoAutomaticaResumo(BaseModel):
    dia_semana: str
    turno: str
    total_grades: int
    total_alocadas: int
    total_sem_alocacao: int
    alocacoes_persistidas: list[Alocacao]
    grades_sem_alocacao: list[str]
    conflitos: list[Conflito]
```

Adicionar endpoint:

```text
POST /api/alocacoes/automatica
```

Body JSON:

```json
{
  "dia_semana": "Segunda",
  "turno": "Manha",
  "sobrescrever": false
}
```

O endpoint deve retornar `AlocacaoAutomaticaResumo`.

## Backend: caminho esperado

1. Importar `alocar` em `src/controllers/alocacao_controller.py`.
2. Criar metodo `alocar_automaticamente(req, usuario="sistema")`.
3. No metodo:
   - carregar `grades = self._grades.listar_grades()`
   - carregar `salas = self._salas.listar_salas()`
   - carregar `restricoes = self._restricoes.listar_restricoes()`
   - carregar `alocacoes_antes = self._alocacoes.listar_alocacoes()`
   - chamar `alocar(req.dia_semana, req.turno, grades, salas, alocacoes_antes)`
   - converter cada `ResultadoAlocacao` alocado em uma ou mais `Alocacao`
   - persistir via `self._alocacoes.atualizar_alocacao(...)`
   - recalcular conflitos finais com `calcular_conflitos(...)`
   - retornar o resumo.
4. Adicionar rota em `src/routers/alocacao.py`.
5. Atualizar testes.

## Frontend: caminho esperado

1. Em `frontend/src/stores/saa.ts`, adicionar action `alocarAutomaticamente(payload)`.
2. A action deve chamar `POST /api/alocacoes/automatica`.
3. Depois de sucesso, recarregar:
   - `buscarAlocacoes()`
   - `buscarResumoDashboard()`
   - `buscarConflitos()`
   - `buscarGrades()`
4. Em `frontend/src/views/SaaAlocacoes.vue` ou `SaaDashboard.vue`, adicionar controles:
   - select de dia
   - select de turno
   - checkbox/toggle "sobrescrever alocacoes existentes"
   - botao "Alocar automaticamente"
   - feedback com resumo da execucao.

## Testes obrigatorios

Atualizar/criar testes para cobrir:

1. `POST /api/alocacoes/automatica` retorna 200 no caso feliz.
2. Cria alocacoes para grades sem sala no dia/turno informado.
3. Nao duplica alocacoes ao rodar duas vezes para o mesmo dia/turno.
4. Com `sobrescrever=false`, preserva alocacoes existentes.
5. Com `sobrescrever=true`, atualiza alocacoes existentes.
6. Respeita salas indisponiveis (`reforma`, `manutencao`, `bloqueada`).
7. Retorna grades sem alocacao quando faltam salas.
8. Recalcula conflitos finais.

## Comandos de verificacao

Antes de finalizar, rodar:

```bash
uv run pytest
uv run ruff check src tests
cd frontend && npm run build
```

Estado atual validado antes deste prompt:

- `uv run pytest`: 113 testes passaram.
- `uv run ruff check src tests`: passou.
- `frontend/npm run build`: passou.

## Cuidados finais

- Nao transformar o motor em codigo que acessa arquivos ou banco. Ele deve continuar puro.
- Nao remover o fluxo manual de criacao/ajuste de alocacoes.
- Nao mexer nos providers AGHU de importacao CSV salvo se houver bug diretamente relacionado.
- Preservar a ideia de que os CSVs anexados pelo usuario sao a fonte atual dos dados.
- Se precisar alterar contrato de resposta, atualizar `frontend/src/stores/saa.ts` e os testes juntos.
