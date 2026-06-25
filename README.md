# SAA — Sistema de Apoio à Alocação Ambulatorial

Aplicação web full-stack (FastAPI + Vue 3) para apoiar a alocação manual de salas
ambulatoriais a partir de dados reais exportados do AGHU (Hospital de Clínicas de Porto Alegre).

> **Documentação técnica da integração AGHU:** [docs/integracao_aghu_csv.md](./docs/integracao_aghu_csv.md)

## Principais Características

- **Backend Moderno:** Construído com FastAPI, oferecendo alta performance, código assíncrono e documentação de API automática (Swagger/OpenAPI).
- **Frontend Reativo:** Utiliza Vue 3 com Vite para uma experiência de desenvolvimento rápida e uma interface de usuário reativa.
- **Arquitetura de Provedores:** Design flexível que permite trocar a fonte de dados de um domínio (ex: PostgreSQL, CSV) alterando uma única variável de configuração no arquivo do roteador, sem modificar o código de negócio.
- **Autenticação Híbrida:** Suporte nativo para autenticação via Active Directory (AD) em produção e um provedor "mock" para desenvolvimento offline (sem necessidade de credenciais de AD).
- **Estrutura Escalável:** Organização de projeto clara que separa responsabilidades (`routers`, `controllers`, `providers`), facilitando a manutenção e a adição de novas funcionalidades.

## Estrutura do Projeto

A estrutura do projeto é projetada para separar claramente as responsabilidades entre backend, frontend e documentação.

```
.
├── data/                 # Dados estáticos (ex: arquivos CSV)
├── docs/                 # Documentação detalhada do projeto
│   ├── ARCHITECTURE.md   # Explicação da arquitetura e padrões
│   ├── AUTHENTICATION.md # Detalhes sobre o sistema de autenticação
│   └── SETUP.md          # Guia de instalação e execução
├── frontend/             # Código-fonte da aplicação Vue.js
├── src/                  # Código-fonte do backend FastAPI
│   ├── auth/             # Lógica de autenticação (AD, Mock, JWT)
│   ├── controllers/      # Lógica de negócio e orquestração
│   ├── dependencies.py   # Fábrica de injeção de dependência
│   ├── models/           # Modelos de dados (SQLAlchemy)
│   ├── providers/        # Camada de acesso a dados (Postgres, CSV, etc.)
│   │   ├── implementations/
│   │   └── interfaces/
│   ├── resources/        # Configuração de recursos (ex: conexão com DB)
│   └── routers/          # Definição dos endpoints da API
├── .env.example          # Arquivo de exemplo para variáveis de ambiente
└── README.md             # Esta documentação
```

## Primeiros Passos

Para instalar e executar a aplicação, siga o guia de configuração detalhado:

- **[Guia de Instalação e Execução (SETUP.md)](./docs/SETUP.md)**

## Início Rápido (Quick Start)

Este projeto utiliza scripts automatizados para facilitar o ambiente:

1. **Configuração Inicial:**
   ```bash
   cp .env.example .env
   ```

2. **Modo Produção Local (Build & Run):**
   Gera o build do frontend e sobe o servidor FastAPI consolidado.
   ```bash
   ./start.sh
   ```

3. **Modo Desenvolvimento (Hot Reload):**
   Sobe o Backend e o Frontend (Vite) em paralelo com atualização instantânea.
   ```bash
   ./dev.sh
   ```

A aplicação estará disponível em `http://localhost:8000` (via start.sh) ou `http://localhost:5173` (via dev.sh).

### Modo Docker (alternativa)

O projeto também inclui `Dockerfile` e `docker-compose.yml` (build multi-stage:
frontend Vue → imagem Python 3.13 com `uv`).

```bash
cp .env.example .env

# Importante: o compose monta ./app.db como arquivo (bind mount). Se ele não
# existir ainda (ex.: checkout novo), o Docker cria um DIRETÓRIO no lugar e o
# backend falha ao abrir o SQLite. Crie o arquivo vazio antes do primeiro run:
touch app.db   # Windows (PowerShell): New-Item -ItemType File app.db

docker compose up --build
```

A aplicação ficará disponível em `http://localhost:8000`.

## Aprofundamento

Para entender a fundo os conceitos e padrões utilizados neste framework, consulte a documentação específica:

- **[Arquitetura do Projeto (ARCHITECTURE.md)](./docs/ARCHITECTURE.md)**
- **[Sistema de Autenticação (AUTHENTICATION.md)](./docs/AUTHENTICATION.md)**

---

## Integração com CSVs Reais do AGHU

O SAA aceita dois formatos de CSV:

### Formato 1 — Grade Simplificada (legado)

Formato antigo, **não é mais usado em produção**. O Dashboard, `/api/grades`
e `/api/alocacoes` agora leem a grade real (`vw_grades.csv`) através de
`GradeAghuDashboardProvider`. O CSV fictício original foi retirado de
`data/` e preservado em `data/legado_ficticio/` apenas como referência.

```
id,especialidade,profissional,dia_semana,turno,qtd_salas_necessarias
G001,Cardiologia,Dr. Silva,Segunda,Manhã,1
```

### Formato 2 — vw_grades.csv (AGHU real)

Exportado diretamente do AGHU. Colunas obrigatórias:

```
Grade,Profissional_Grade,Unidade_Funcional,Condicao_De_Atendimento,Especialidade,
Situacao_Atual_Grade,Dia_da_Semana,Turno,Situacao_Atual_Horario,Quantidade_Vagas
```

`Hora_Inicio` é opcional. Colunas extras são ignoradas.

### Formato 3 — vw_consultas_2026.csv (AGHU real)

Colunas obrigatórias mínimas:

```
Situacao_Consulta, Consulta_Excedente, Especialidade
```

Aceita múltiplos nomes de coluna (ex: `Num_Consulta` ou `Num_Consulta_Aghu`).

### Por que Quantidade_Vagas ≠ Número de Salas?

`Quantidade_Vagas` representa a **capacidade de atendimento planejada** pelo AGHU
(quantas consultas foram programadas). Não corresponde ao número de salas físicas.

No MVP, `qtd_salas_necessarias = 1` por grade/horário/profissional.

---

## Como Importar os CSVs

### Via interface web (recomendado)

1. Acesse `/saa/qualidade-dados` na sidebar do sistema.
2. Clique em "Selecionar arquivo" para `vw_grades.csv` ou `vw_consultas_2026.csv`.
3. O sistema valida, salva em `data/importados/` e recalcula os indicadores.

### Via API (curl)

```bash
# Importar grades
curl -X POST http://localhost:8000/api/importacao/aghu/grades \
  -F "arquivo=@vw_grades.csv"

# Importar consultas
curl -X POST http://localhost:8000/api/importacao/aghu/consultas \
  -F "arquivo=@vw_consultas_2026.csv"
```

Resposta:

```json
{
  "arquivo": "vw_grades.csv",
  "linhas_lidas": 5695,
  "linhas_validas": 5440,
  "registros_unicos": 2029,
  "avisos": ["Existem 255 linhas sem dia da semana"]
}
```

---

## Endpoints AGHU Adicionados

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/aghu/grades` | Listar grades AGHU (filtros + paginação) |
| `GET` | `/api/aghu/grades/resumo` | Resumo da importação de grades |
| `GET` | `/api/aghu/consultas` | Listar consultas (paginado, filtros) |
| `GET` | `/api/aghu/consultas/resumo` | Resumo da importação de consultas |
| `GET` | `/api/aghu/consultas/por-especialidade` | Agregado por especialidade |
| `GET` | `/api/aghu/consultas/por-dia-turno` | Agregado por dia × turno |
| `GET` | `/api/aghu/consultas/excedentes` | Apenas consultas excedentes |
| `GET` | `/api/aghu/capacidade/resumo` | Indicadores de capacidade geral |
| `GET` | `/api/aghu/qualidade-dados` | Painel de qualidade dos dados |
| `POST` | `/api/importacao/aghu/grades` | Upload de vw_grades.csv |
| `POST` | `/api/importacao/aghu/consultas` | Upload de vw_consultas_2026.csv |

### Paginação e filtros em `/api/aghu/consultas`

```
GET /api/aghu/consultas?limit=100&offset=0
GET /api/aghu/consultas?especialidade=CARDIOLOGIA
GET /api/aghu/consultas?apenas_excedentes=true
GET /api/aghu/consultas?turno=MANHÃ&dia_semana=SEGUNDA
```

---

## Indicadores Calculados

| Indicador | Descrição |
|-----------|-----------|
| `consultas_marcadas` | Situação AGENDADO / MARCADO / CONFIRMADO |
| `vagas_livres` | Situação LIVRE / DISPONÍVEL |
| `bloqueios` | Situação BLOQUEADO / BLOQUEIO |
| `consultas_excedentes` | Flag `Consulta_Excedente = S` |
| `taxa_ocupacao` | marcadas / (marcadas + livres) |
| `taxa_excedente` | excedentes / total de consultas |

---

## Como Rodar os Testes

```bash
# Backend
pytest tests/ -v

# Testes específicos dos CSVs AGHU
pytest tests/test_grade_aghu_csv_provider.py -v
pytest tests/test_consulta_aghu_csv_provider.py -v
pytest tests/test_capacidade_service.py -v
```
