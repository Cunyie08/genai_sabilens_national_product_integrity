"""
Database connection and session management — owned by tunjipaul.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings

class Base(DeclarativeBase):
    pass

# 1. Start with the base connection arguments required for Cloud SQL / pgbouncer
db_connect_args = {
    "statement_cache_size": 0,
}

# 2. Dynamically add the SSL requirement ONLY if it is explicitly set in the environment
if hasattr(settings, 'DB_SSL_MODE') and settings.DB_SSL_MODE:
    db_connect_args["ssl"] = settings.DB_SSL_MODE

# 3. Create async engine.
engine = create_async_engine(
    # Strip sslmode from the URL string so asyncpg doesn't crash
    settings.DATABASE_URL.replace("?sslmode=require", "").replace("?sslmode=disable", ""),
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    connect_args=db_connect_args, # Pass the dynamically built dictionary once
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
