# SAA — Sistema de Alocação Ambulatorial

Aloca as grades de atendimento das clínicas do HC nos pavimentos do prédio, para
a semana inteira, a partir da exportação de grades do AGHU.

O gestor importa a planilha, o sistema trata os dados, executa o motor de
alocação e permite ajustar o resultado. Cada alocação é um **cenário
autocontido**: guarda sua própria cópia dos insumos, de modo que reabrir um
cenário antigo mostra exatamente o que gerou aquele resultado.

Uso local, um gestor por vez — sem login e sem controle de concorrência.

## Como funciona

O gestor percorre 6 etapas, podendo voltar a qualquer uma:

| # | Etapa | O que faz |
|---|---|---|
| 1 | Importação | Lê a grade do AGHU e trata os dados |
| 2 | Grades | Confere a demanda e escolhe quais unidades participam |
| 3 | Panorama de salas | Informa quantas salas de cada tipo há em cada pavimento |
| 4 | Restrições | Define obrigatoriedades e preferências |
| 5 | Execução | Roda o motor de alocação |
| 6 | Ajustes | Corrige o resultado à mão |

Mexer nas etapas 1 a 4 marca a alocação como **desatualizada** — o sistema avisa
em vez de apagar, e o gestor decide se refaz.

### As duas ideias centrais

**Alocação por clínica, não por sala.** Cada clínica vai inteira para um
pavimento e fica lá a semana toda. O que varia entre turnos é quantas salas ela
usa, não o pavimento.

**Capacidade em estações.** Uma sala de 2 estações comporta dois atendimentos ao
mesmo tempo e vale 2 na conta. O gestor edita as contagens de salas por tipo; a
capacidade é sempre derivada, nunca digitada.

## Requisitos

- **Python 3.13+**
- **Node.js 18+**
- **[uv](https://docs.astral.sh/uv/)** — gerenciador de dependências Python

## Instalação

```bash
git clone <url-do-repositorio>
```

```bash
cd appstartTeam1
```

Instale as dependências do backend (o `uv` cria o ambiente virtual sozinho):

```bash
uv sync
```

E as do frontend:

```bash
npm --prefix frontend install
```

Copie o arquivo de ambiente. O padrão já funciona para uso local:

```bash
cp .env.example .env
```

No Windows (PowerShell), use `Copy-Item .env.example .env`.

## Execução

São dois processos, em terminais separados.

**Terminal 1 — backend.** As migrações do banco são aplicadas automaticamente no
startup; não é preciso rodar Alembic à mão:

```bash
uv run uvicorn src.main:app --port 8000
```

**Terminal 2 — frontend:**

```bash
npm --prefix frontend run dev
```

Abra **http://localhost:5173**. A documentação interativa da API fica em
**http://localhost:8000/docs**.

## Testes

Backend:

```bash
uv run pytest
```

Frontend:

```bash
npm --prefix frontend test
```

Verificação de tipos do frontend:

```bash
npm --prefix frontend run build
```

## Estrutura

```
src/
├─ domain/          Regras de negócio em Python puro — sem FastAPI, sem banco
│  ├─ entidades.py     Malha de 10 turnos, capacidade em estações
│  ├─ processo.py      As 6 etapas e a regra de invalidação
│  ├─ importacao/      Pipeline de tratamento da planilha do AGHU
│  └─ alocacao/        Motor de alocação (interface + heurística)
├─ services/        Casos de uso — orquestra as etapas
├─ repositories/    Único ponto que fala com o banco
├─ models/          Modelos ORM (SQLAlchemy)
├─ routers/         Endpoints da API
└─ resources/       Conexão com o SQLite

frontend/src/
├─ components/      PlanilhaEditavel (reusada nas etapas 2, 3 e 6), Stepper
├─ views/           Importação e Cenário
└─ services/        Cliente HTTP
```

A regra de ouro das camadas: **API → Serviço → Domínio → Repositório**. Cada uma
só chama a de baixo. O domínio não sabe que existe HTTP nem banco, e por isso
pode ser executado por um script:

```bash
uv run python -c "from src.domain.importacao import importar; print(importar('caminho/para/vw_grades.csv').relatorio.resumo())"
```

## Banco de dados

SQLite em arquivo único (`saa.db`), criado no primeiro startup. O esquema é
versionado com Alembic.

Ao alterar os modelos em `src/models/`, gere a migração **contra um banco
limpo** — se você apontar para um banco que já tem as tabelas, o autogenerate
não encontra diferença nenhuma e produz uma migração vazia:

```bash
SQLITE_DSN="sqlite+aiosqlite:///tmp_limpo.db" uv run alembic revision --autogenerate -m "descrição"
```

O teste `test_a_migracao_cria_as_mesmas_tabelas_dos_modelos` existe justamente
para pegar esse descuido.

## Documentação

- **[docs/SETUP.md](docs/SETUP.md)** — instalação passo a passo e solução de problemas
- **[docs/spec/](docs/spec/)** — especificação de requisitos (SRD) do projeto

> **Atenção:** a SRD em `docs/spec/` ainda descreve o modelo anterior, em que a
> alocação era feita de grade para sala específica. O sistema foi reescrito para
> alocar clínica em pavimento, conforme o documento de arquitetura de julho de
> 2026. Os arquivos `04-modelo-dados.md` e `06-arquitetura.md` são os mais
> defasados.

## Dados de referência

O mapa real do HC (10 pavimentos, 231 estações) e a lista oficial de unidades do
ambulatório (43 das 62 participam) estão embutidos em
[`src/repositories/dados_referencia.py`](src/repositories/dados_referencia.py),
extraídos das planilhas "Quantitativo de Consultórios" e "Grades AGHU -
Validação". São semeados no catálogo na primeira execução.

Para trocar por dados de outra unidade, edite esse módulo e apague o `saa.db`
para forçar a resemeadura.

## Pendências conhecidas

- **Decisões de produto da seção 13 do documento.** Distribuição concentrada
  vs. espalhada quando não há preferência; pesos do histórico na afinidade; se a
  visualização precisa exportar para Excel/PDF. Aguardam definição do cliente.
- **A SRD em `docs/spec/` descreve o modelo antigo** (grade → sala). Precisa ser
  atualizada para o modelo clínica → pavimento.
