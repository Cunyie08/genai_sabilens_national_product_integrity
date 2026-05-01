"""
Database connection and session management — owned by tunjipaul.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


# Create async engine.
# NOTE: Cloud SQL PostgreSQL — direct connection on port 5432 via public IP.
# Use the Cloud SQL Auth Proxy or Cloud SQL Python Connector for private-IP / IAM auth.
# - statement_cache_size=0 is required when using Cloud SQL Connector or pgbouncer.
# - ssl='require' enforces TLS for Cloud SQL connections (recommended for production).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,
        # This will look for a variable in your .env, or default to False locally
        "ssl": settings.DB_SSL_MODE if hasattr(settings, 'DB_SSL_MODE') else False,
    },
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """Dependency to get database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
