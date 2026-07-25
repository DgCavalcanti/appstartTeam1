# Arquitetura

## 1. Stack Técnica
* **Frontend**
    - Vue 3 + TypeScript + Vite
    - Pinia (estado), Vue Router, Axios
    - Tailwind CSS
    - Vitest + Vue Test Utils (testes)
* **Backend**
    - Python + FastAPI + Pydantic
    - SQLAlchemy (ORM) + Alembic (migrações)
    - pandas (tratamento da importação)
    - pytest (testes)
* **Banco de Dados**
    - SQLite em arquivo único (`saa.db`), esquema versionado por Alembic

## 2. Camadas
A regra de ouro: cada camada só chama a de baixo, nunca a de cima.

```
Frontend (Vue) → API (FastAPI routers) → Serviços → Domínio (Python puro) → Repositórios (SQLAlchemy) → SQLite
```

| Camada | Responsabilidade |
|---|---|
| **API** (routers) | Recebe HTTP, valida entrada/saída, devolve JSON. Sem regra de negócio. |
| **Serviços** | Orquestra cada operação e a máquina de estados das 6 etapas. |
| **Domínio** | As regras de verdade — pipeline de importação e motor de alocação — em Python puro, sem FastAPI nem banco. |
| **Repositórios** | Único ponto que fala com o banco; traduz entidades ⇄ tabelas. |

O **domínio isolado** permite testar e evoluir o algoritmo com scripts, sem subir a aplicação. O motor fica atrás de uma interface (`SolverAlocacao`, padrão Strategy), de modo que a heurística possa ser trocada por um solver exato sem tocar em API, banco ou telas.

## 3. Uso local
* Aplicação de uso local por um único gestor: sem autenticação, sem filas, sem controle de concorrência.
* Não há acesso direto ao AGHU nem escrita de volta nele; a entrada é a grade exportada.
* Dados de pacientes não entram no escopo — a grade tratada guarda profissional, dia e turno, não dados clínicos.

## 4. Estrutura de arquivos
```
src/
├── main.py                # fábrica da aplicação FastAPI + startup (migrações, semeadura)
├── domain/                # REGRAS — Python puro, sem FastAPI nem banco
│   ├── entidades.py       # malha de 10 turnos, capacidade em estações
│   ├── processo.py        # as 6 etapas e a regra de invalidação
│   ├── importacao/        # pipeline de tratamento (leitor, regras, pipeline)
│   └── alocacao/          # motor: solver (interface) + heuristica
├── services/              # casos de uso: processo, grades, panorama,
│                          #   restricoes, alocacao, visualizacao
├── repositories/          # acesso ao banco + catálogo (dados_referencia)
├── models/                # modelos ORM (tabelas da seção 4)
├── routers/               # blueprints da API (importacao, cenarios)
└── resources/             # conexão com o SQLite
alembic/                   # migrações
tests/                     # testes — foco no domínio (importação e alocação)

frontend/src/
├── views/                 # SaaImportacao, SaaCenario, SaaVisualizacao
├── components/            # PlanilhaEditavel, Stepper, FiltroAlocacao,
│                          #   MedidorOcupacao
├── services/              # cliente axios
└── router/                # rotas
```

## 5. Guardrails para IA (SDD)

### Escopo Positivo (O que fazer)
- Manter as regras de negócio no domínio, em Python puro e testável isoladamente.
- Respeitar o fluxo em camadas: API → Serviço → Domínio → Repositório.
- Capacidade sempre derivada das contagens de salas, nunca digitada.
- Cada alocação é um cenário autocontido; reprocessar cria/atualiza, não apaga.
- Criar testes para cada nova regra de domínio, serviço ou componente.
- Gerar migração Alembic contra um banco limpo ao alterar os modelos.

### Escopo Negativo (Anti-Patterns)
- O router não contém regra de negócio; o frontend só consome a API.
- Não persistir as linhas brutas do AGHU — só grade_slot e grade_demanda.
- Não fazer o cliente digitar capacidade; ela é derivada no domínio.
- Não deixar a preferência forçar sobra — só a obrigatoriedade força.
- Não acessar nem escrever no AGHU diretamente.
- Não introduzir autenticação, RBAC ou multiusuário sem mudança explícita de escopo (o sistema é de uso local).
