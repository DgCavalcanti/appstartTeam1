# Copilot / AI Agent Instructions for this repository

Purpose: give an AI coding agent the minimal, actionable knowledge to be productive in this FastAPI + Vue.js monorepo.

- **Big picture:** Backend is a FastAPI monolith in `src/` and the frontend is a Vue 3 Vite app in `frontend/`. The backend mounts a built frontend at `src/static/dist` and exposes REST routers from `src/routers`.

- **Key files to read first:**
  - [src/main.py](src/main.py) — app lifecycle, DB managers, router inclusion.
  - [src/resources/database.py](src/resources/database.py) — `DatabaseManager`, `get_app_db_session`, `get_aghu_db_session` dependency patterns.
  - [src/providers/interfaces/paciente_provider_interface.py](src/providers/interfaces/paciente_provider_interface.py) — example provider contract (async methods `listar_pacientes`, `obter_paciente_por_codigo`).
  - `src/providers/implementations/` — concrete data sources (CSV, Postgres). Follow the interface shape there.
  - [frontend/src/main.ts](frontend/src/main.ts) and `frontend/package.json` — frontend bootstrapping and scripts.

- **Architecture notes & patterns:**
  - Providers implement an async interface (see `PacienteProviderInterface`). Use async I/O everywhere when interacting with DB or files.
  - Database connections are created at app lifespan and stored on `app.state` as `app_db` (SQLite) and optionally `aghu_db` (Postgres). Use dependency functions from `src/resources/database.py` to obtain sessions in routers/controllers.
  - Routers in `src/routers` register provider selection/config at router level — prefer changing provider wiring there rather than modifying business logic.

- **Dev & run workflows (project-specific):**
  - Copy environment file: `cp .env.example .env` and set `SQLITE_DSN` (required) and `POSTGRES_DSN` (optional).
  - Development (backend + vite): run `./dev.sh` from repo root to start both backend and frontend with hot reload.
  - Build & run production bundle: run `./start.sh` which builds the frontend into `src/static/dist` and starts the FastAPI server.
  - Alternative direct backend run: `uvicorn src.main:app --reload --port 8000` (from repo root).
  - Frontend only: `cd frontend && npm install && npm run dev` or `npm run build` for production assets.
  - Migrations: use `alembic` (see `alembic/` and `alembic.ini`) for DB schema changes; the code creates SQLite tables on startup only for dev convenience.

- **Environment / dependencies:**
  - Project requires Python >= 3.13 (see `pyproject.toml`). Key env vars: `SQLITE_DSN` (required), `POSTGRES_DSN` (optional). `.env.example` is present.
  - Backend is synchronous entry `app` but expects async DB engines (`sqlalchemy.ext.asyncio` + `aiosqlite` / `asyncpg`).

- **Testing & debugging hints specific to this repo:**
  - DB sessions are provided via dependency injection; to write controller tests, mock or create a `DatabaseManager` and set it on a test FastAPI app `app.state`.
  - Provider implementations are small and isolated; unit test them directly (e.g., CSV provider reads `data/pacientes.csv`).

- **Conventions to follow when editing code:**
  - Keep async/await across provider → controller → router stacks.
  - Do not change provider contracts; add new providers under `src/providers/implementations` and wire them in the corresponding router.
  - Use `app.state` for long-lived resources created in the lifespan context defined in `src/main.py`.

If any section is unclear or you want more examples (router wiring, provider tests, or a sample PR), tell me which area to expand.
