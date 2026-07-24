# Guia de Instalação e Execução

Passo a passo para deixar o SAA rodando a partir de um clone limpo, no Windows,
Linux ou macOS.

## 1. Ferramentas necessárias

| Ferramenta | Versão | Para quê |
|---|---|---|
| Python | 3.13+ | Backend |
| Node.js | 18+ | Frontend |
| uv | qualquer | Gerencia o ambiente e as dependências Python |

Para instalar o `uv`:

```bash
pip install uv
```

Ou siga as instruções oficiais em <https://docs.astral.sh/uv/>.

## 2. Dependências

Na raiz do projeto:

```bash
uv sync
```

O `uv` cria o ambiente virtual em `.venv/` e instala tudo — inclusive `pytest` e
`httpx`, que ficam no grupo `dev`. Não é preciso ativar o ambiente à mão: os
comandos abaixo usam `uv run`.

Frontend:

```bash
npm --prefix frontend install
```

## 3. Variáveis de ambiente

```bash
cp .env.example .env
```

No Windows (PowerShell):

```bash
Copy-Item .env.example .env
```

O arquivo tem três variáveis e o padrão já serve para uso local. A única que
importa é `SQLITE_DSN`, que aponta para o arquivo do banco.

## 4. Banco de dados

Não é preciso fazer nada. O backend aplica as migrações do Alembic no startup e
cria o `saa.db` se ele não existir.

Se quiser aplicar à mão:

```bash
uv run alembic upgrade head
```

## 5. Executar

Dois processos, em terminais separados.

**Backend:**

```bash
uv run uvicorn src.main:app --port 8000
```

**Frontend:**

```bash
npm --prefix frontend run dev
```

A aplicação fica em <http://localhost:5173> e a documentação da API em
<http://localhost:8000/docs>.

O servidor do Vite encaminha `/api` para o backend na porta 8000 — por isso os
dois precisam estar no ar.

## 6. Testes

```bash
uv run pytest
```

```bash
npm --prefix frontend test
```

## Problemas comuns

**`ModuleNotFoundError: No module named 'src'`**
Rode os comandos a partir da raiz do projeto, não de dentro de `src/` ou
`tests/`.

**A tela carrega mas todas as chamadas dão 404 com "API route not found"**
O backend não está no ar, ou está rodando uma versão antiga do código. O
`uvicorn` não recarrega sozinho: se você alterou arquivos em `src/`, reinicie-o.
Para recarregar automaticamente durante o desenvolvimento, acrescente `--reload`.

**Erro de porta em uso**
Outro processo está na 8000 ou na 5173. Encerre-o ou troque a porta — se mudar a
do backend, ajuste também o `proxy` em `frontend/vite.config.ts`.

**`uv sync` remove pacotes que eu tinha instalado**
É o comportamento esperado: o `uv` deixa o ambiente igual ao declarado no
`pyproject.toml`. Se precisa de uma biblioteca nova, adicione-a lá em vez de
instalar direto com `pip`.

**Migração gerada em branco**
O `alembic revision --autogenerate` compara os modelos com o banco apontado pelo
`SQLITE_DSN`. Se esse banco já tem as tabelas, ele não encontra diferença e gera
uma migração vazia. Gere sempre contra um banco limpo:

```bash
SQLITE_DSN="sqlite+aiosqlite:///tmp_limpo.db" uv run alembic revision --autogenerate -m "descrição"
```

**O frontend abre mas mostra uma tela antiga**
O backend também serve um build estático em `src/static/dist`, que pode estar
desatualizado. Durante o desenvolvimento use sempre a porta 5173 (Vite), não a
8000.
