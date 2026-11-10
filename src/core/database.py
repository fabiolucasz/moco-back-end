from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from src.config import get_settings

settings = get_settings()

engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE if "sqlite" not in settings.DATABASE_URL else None,
    max_overflow=(
        settings.DB_MAX_OVERFLOW if "sqlite" not in settings.DATABASE_URL else None
    ),
    future=True,
    # Disable prepared statement cache for pgbouncer compatibility
    connect_args=(
        {
            "statement_cache_size": 0,
            "prepared_statement_cache_size": 0,
        }
        if "postgresql" in settings.DATABASE_URL
        else {}
    ),
)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Base model class with AsyncAttrs support for SQLAlchemy 2.x."""

    pass


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an isolated async database session per request."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
