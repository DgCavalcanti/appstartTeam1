from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import asyncio
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

from . import models  # noqa: F401 — registra as tabelas do SAA em Base.metadata
from .resources.database import DatabaseManager


def _aplicar_migracoes() -> None:
    """
    Leva o banco até a última revisão do Alembic.

    Roda numa thread separada porque o env.py do Alembic chama asyncio.run(),
    o que não é permitido de dentro do loop já em execução do FastAPI.

    Deliberadamente NÃO usamos Base.metadata.create_all aqui: ele criaria as
    tabelas por fora do controle de versão, o que faz o autogenerate comparar
    contra um banco já atualizado e gerar migrações vazias — um erro silencioso
    que só aparece quando alguém clona o projeto e fica sem esquema nenhum.
    """
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config("alembic.ini"), "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up...")

    # Banco da aplicação (SQLite) — única persistência do SAA
    app_dsn = os.getenv("SQLITE_DSN")
    if not app_dsn:
        raise ValueError("SQLITE_DSN not found in environment variables.")

    await asyncio.to_thread(_aplicar_migracoes)
    print("Migrações aplicadas.")

    app.state.app_db = DatabaseManager(app_dsn)
    print("App SQLite connection pool initialized.")

    yield

    # Shutdown
    print("Shutting down...")
    if hasattr(app.state, 'app_db') and app.state.app_db:
        await app.state.app_db.close_connection()
        print("App SQLite connection pool closed.")

app = FastAPI(
    title="SAA — Sistema de Alocação Ambulatorial",
    description="Alocação de grades de clínicas em pavimentos do HC. Uso local, gestor único.",
    version="2.0.0",
    lifespan=lifespan,
)

# Serve o frontend Vue 3 empacotado
app.mount("/assets", StaticFiles(directory="src/static/dist/assets"), name="assets")
# Outros arquivos estáticos na raiz do dist (como favicon.ico)
app.mount("/static", StaticFiles(directory="src/static/dist"), name="static")

from .routers import cenarios, importacao
app.include_router(importacao.router)
app.include_router(cenarios.router)

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """
    Serve o arquivo index.html para todas as rotas que não são da API ou arquivos estáticos.
    Isso é necessário para que o roteamento do Vue (SPA) funcione.
    """
    # Se a rota começa com 'api', deixa o roteador do FastAPI lidar
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")

    index_path = os.path.join("src", "static", "dist", "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend build not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
