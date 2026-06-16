# =============================================================================
# SAA - imagem unica (backend FastAPI + frontend Vue buildado)
# Banco de app em SQLite (sem Postgres). Uso pessoal / demo local.
# =============================================================================

# --- Stage 1: build do frontend (Vue 3 + Vite) ------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /app
COPY . .
WORKDIR /app/frontend
RUN npm ci
RUN npm run build
# Vite escreve o build em /app/src/static/dist (ver frontend/vite.config.ts)

# --- Stage 2: backend (FastAPI + uv) servindo o frontend buildado ----------
FROM python:3.13-slim AS final
WORKDIR /app

RUN pip install --no-cache-dir uv

# Dependencias primeiro (aproveita cache de camada quando so o codigo muda)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen

# Resto do codigo
COPY . .

# Sobrescreve com o build feito no stage anterior
COPY --from=frontend-build /app/src/static/dist ./src/static/dist

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
