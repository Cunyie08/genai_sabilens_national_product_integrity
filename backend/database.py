"""
Database connection and session management — owned by tunjipaul.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


# Create async engine.
# NOTE: Supabase uses pgbouncer in transaction mode (port 6543).
# - statement_cache_size=0 disables prepared statement caching in asyncpg
#   (required to avoid DuplicatePreparedStatementError with pgbouncer).
# - ssl='require' enforces SSL for Supabase connections (Supabase requires SSL).
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    connect_args={
        "statement_cache_size": 0,  # Required for pgbouncer transaction mode
        "ssl": "require",           # Required for Supabase SSL enforcement
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
