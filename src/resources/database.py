# src/resources/database.py

from typing import AsyncGenerator
from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Base para os modelos do banco de dados da aplicação (SQLite)
Base = declarative_base()

class DatabaseManager:
    """
    Manages asynchronous database connections and sessions for a specific DSN.
    """
    def __init__(self, dsn: str):
        self.engine: AsyncEngine = create_async_engine(dsn, echo=False) # Set echo=False to reduce log verbosity
        self.async_session_maker = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Provides an asynchronous session for database operations.
        """
        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()

    async def close_connection(self):
        """
        Closes all connections in the engine's connection pool.
        """
        await self.engine.dispose()

async def get_aghu_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get an AGHU database session from the app state.

    Levanta um 503 claro (em vez de AttributeError/NoneType) quando POSTGRES_DSN
    não foi configurado e o pool nunca foi inicializado no lifespan — corrigido
    na auditoria técnica, já que esse caminho era um crash não tratado.
    """
    aghu_db_manager: DatabaseManager | None = getattr(request.app.state, "aghu_db", None)
    if aghu_db_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados AGHU (PostgreSQL) não configurado. Defina POSTGRES_DSN no .env.",
        )
    async for session in aghu_db_manager.get_session():
        yield session

async def get_app_db_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for FastAPI to get an application database session (SQLite) from the app state.
    """
    app_db_manager: DatabaseManager = request.app.state.app_db
    async for session in app_db_manager.get_session():
        yield session
