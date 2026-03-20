"""Alembic migration environment"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context
import os
import sys

# Add repo root to path so backend.* imports resolve.
# Path: backend/alembic/env.py → backend/alembic → backend → repo_root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from backend.config import settings
from backend.models.user import Base as UserBase
from backend.models.company import Base as CompanyBase
from backend.models.product import Base as ProductBase
from backend.models.scan import Base as ScanBase
from backend.models.alert import Base as AlertBase
from backend.models.analytics import Base as AnalyticsBase

# Combine all metadata
metadata = UserBase.metadata

config = context.config


if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _sync_url(url: str) -> str:
    """Replace asyncpg driver with psycopg2 for synchronous Alembic migrations."""
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


def run_migrations_offline() -> None:
    """Run migrations in offline mode"""
    url = _sync_url(settings.DATABASE_URL)
    context.configure(
        url=url,
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = _sync_url(settings.DATABASE_URL)

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
