from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

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

    # Semeia o catálogo (mapa do HC + unidades do ambulatório) se ainda vazio.
    from .repositories import CatalogoRepository

    async for sessao in app.state.app_db.get_session():
        semeado = await CatalogoRepository(sessao).semear_referencia()
        await sessao.commit()
        if any(semeado.values()):
            print(f"Catálogo semeado: {semeado}")

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

# Frontend Vue 3 empacotado. É artefato de build e não vai para o repositório,
# então só montamos o que existe: num clone limpo, `StaticFiles` apontando para
# um diretório ausente derruba a aplicação já na importação, e o backend nem
# chegaria a subir. Em desenvolvimento o Vite serve o frontend na porta 5173.
DIST = Path("src/static/dist")

if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")
if DIST.is_dir():
    app.mount("/static", StaticFiles(directory=DIST), name="static")

from .routers import cenarios, importacao, padroes
app.include_router(importacao.router)
app.include_router(cenarios.router)
app.include_router(padroes.router)

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """
    Serve o arquivo index.html para todas as rotas que não são da API ou arquivos estáticos.
    Isso é necessário para que o roteamento do Vue (SPA) funcione.
    """
    # Se a rota começa com 'api', deixa o roteador do FastAPI lidar
    if full_path.startswith("api"):
        raise HTTPException(status_code=404, detail="API route not found")

    index_path = DIST / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # Sem build empacotado. Em desenvolvimento isso é o normal — quem chegou
    # aqui provavelmente abriu a porta do backend em vez da do Vite.
    return {
        "erro": "O frontend não está empacotado neste servidor.",
        "em_desenvolvimento": "Abra http://localhost:5173 (servidor do Vite).",
        "api": "A documentação da API está em /docs.",
        "para_empacotar": "npm --prefix frontend run build",
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
