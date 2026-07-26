# syntax=docker/dockerfile:1
#
# Imagem única: builda o frontend (Vue) e serve tudo — API + SPA — a partir do
# FastAPI, exatamente como `src/main.py` já espera (monta `src/static/dist`).
# Não há dois processos como no dev (Vite + Uvicorn): em produção o Vite só
# gera arquivos estáticos, e quem serve é o próprio backend.

# ---------------------------------------------------------------------------
# Estágio 1 — build do frontend
# ---------------------------------------------------------------------------
FROM node:22-slim AS frontend

WORKDIR /frontend

# Copia só os manifestos primeiro para o cache do Docker não invalidar a
# instalação de dependências a cada mudança de código.
COPY frontend/package.json frontend/package-lock.json ./
# `npm ci` exige o lockfile em sincronia exata com o package.json — o
# lockfile deste projeto está desatualizado (faltam entradas resolvidas por
# dependências opcionais). `npm install` resolve e atualiza o lockfile aqui
# dentro da imagem sem exigir isso.
RUN npm install --no-audit --no-fund

COPY frontend/ ./
# `vite.config.ts` manda o build para ../src/static/dist — ou seja, para fora
# de /frontend. Resolve para /src/static/dist dentro desta imagem.
RUN npm run build


# ---------------------------------------------------------------------------
# Estágio 2 — backend + frontend empacotado
# ---------------------------------------------------------------------------
FROM python:3.13-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENV=production \
    LOG_LEVEL=info \
    SQLITE_DSN=sqlite+aiosqlite:////data/saa.db

WORKDIR /app

# Dependências do backend. `requirements.txt` é o export travado do uv —
# reprodutível sem precisar instalar o uv na imagem.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Código da aplicação e as migrações do Alembic (rodam sozinhas no startup —
# ver `_aplicar_migracoes` em src/main.py).
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# O frontend empacotado no estágio anterior.
COPY --from=frontend /src/static/dist ./src/static/dist

# O SQLite mora aqui — monte um volume para não perder os cenários entre
# reinícios do container.
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
