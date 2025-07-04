from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import get_settings


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self):
        self.settings = get_settings()
        self._engine = None
        self._async_engine = None
        self._session_factory = None
        self._async_session_factory = None

    @property
    def engine(self):
        """Get synchronous database engine."""
        if self._engine is None:
            # Convert async URL to sync URL for SQLAlchemy
            sync_url = self.settings.database.database_url.replace("postgresql+asyncpg://", "postgresql://")
            self._engine = create_engine(
                sync_url,
                echo=self.settings.api.debug,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._engine

    @property
    def async_engine(self):
        """Get asynchronous database engine."""
        if self._async_engine is None:
            # Ensure async URL format
            async_url = self.settings.database.database_url
            if not async_url.startswith("postgresql+asyncpg://"):
                async_url = async_url.replace("postgresql://", "postgresql+asyncpg://")
            
            self._async_engine = create_async_engine(
                async_url,
                echo=self.settings.api.debug,
                pool_pre_ping=True,
                pool_recycle=3600,
            )
        return self._async_engine

    @property
    def session_factory(self):
        """Get synchronous session factory."""
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
            )
        return self._session_factory

    @property
    def async_session_factory(self):
        """Get asynchronous session factory."""
        if self._async_session_factory is None:
            self._async_session_factory = async_sessionmaker(
                bind=self.async_engine,
                class_=AsyncSession,
                autocommit=False,
                autoflush=False,
            )
        return self._async_session_factory

    def get_session(self) -> Session:
        """Get a synchronous database session."""
        return self.session_factory()

    @asynccontextmanager
    async def get_async_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an asynchronous database session."""
        async with self.async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def close(self):
        """Close database connections."""
        if self._async_engine:
            await self._async_engine.dispose()
        if self._engine:
            self._engine.dispose()


# Global database manager instance
db_manager = DatabaseManager()


# Dependency for FastAPI
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with db_manager.get_async_session() as session:
        yield session


# Sync version for Celery tasks
def get_sync_db_session() -> Session:
    """Get synchronous session for Celery tasks."""
    return db_manager.get_session()