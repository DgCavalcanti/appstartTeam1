import logging

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env", override=True)

logger = logging.getLogger(__name__)

from .resources.database import DatabaseManager, Base

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up...")

    aghu_dsn = os.getenv("POSTGRES_DSN")
    if aghu_dsn:
        app.state.aghu_db = DatabaseManager(aghu_dsn)
        logger.info("AGHU PostgreSQL connection pool initialized.")
    else:
        logger.warning("POSTGRES_DSN not found. Skipping AGHU DB initialization.")

    # Aceita SQLITE_DSN ou APP_DB_URL (backward-compat)
    app_dsn = os.getenv("SQLITE_DSN") or os.getenv("APP_DB_URL")
    if not app_dsn:
        raise ValueError("SQLITE_DSN (ou APP_DB_URL) não encontrado nas variáveis de ambiente.")
    app.state.app_db = DatabaseManager(app_dsn)
    logger.info("App SQLite connection pool initialized.")

    async with app.state.app_db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("App SQLite tables checked/created.")

    yield

    logger.info("Shutting down...")
    if hasattr(app.state, 'aghu_db') and app.state.aghu_db:
        await app.state.aghu_db.close_connection()
        logger.info("AGHU PostgreSQL connection pool closed.")
    if hasattr(app.state, 'app_db') and app.state.app_db:
        await app.state.app_db.close_connection()
        logger.info("App SQLite connection pool closed.")

app = FastAPI(
    title="SAA — Sistema de Apoio à Alocação Ambulatorial",
    description="API de apoio à decisão para alocação de salas ambulatoriais.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Arquivos estáticos do frontend (montagem condicional) ─────────────────────
# Em desenvolvimento, o build pode não existir ainda — não quebrar o backend.
_dist_assets = os.path.join("src", "static", "dist", "assets")
_dist_root   = os.path.join("src", "static", "dist")

if os.path.isdir(_dist_assets):
    app.mount("/assets", StaticFiles(directory=_dist_assets), name="assets")

if os.path.isdir(_dist_root):
    app.mount("/static", StaticFiles(directory=_dist_root), name="static")

# ── Routers existentes ────────────────────────────────────────────────────────
from .routers import paciente, auth, admin, aih, bpa, material
app.include_router(paciente.router)
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(aih.router)
app.include_router(bpa.router)
app.include_router(material.router)

# ── Routers SAA ───────────────────────────────────────────────────────────────
from .routers import grade as grade_router
from .routers import sala as sala_router
from .routers import restricao as restricao_router
from .routers import alocacao as alocacao_router
from .routers import dashboard as dashboard_router

app.include_router(grade_router.router)
app.include_router(sala_router.router)
app.include_router(restricao_router.router)
app.include_router(alocacao_router.router)
app.include_router(dashboard_router.router)

# ── Routers AGHU (dados reais) ────────────────────────────────────────────────
from .routers import aghu as aghu_router
from .routers import importacao as importacao_router

app.include_router(aghu_router.router)
app.include_router(importacao_router.router)

# ── SPA fallback ──────────────────────────────────────────────────────────────
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")

    index_path = os.path.join("src", "static", "dist", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Backend running. Frontend build not found — run `npm run build` inside frontend/."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
