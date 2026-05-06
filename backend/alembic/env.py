"""Alembic migration environment."""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the repo root importable so `from backend.xxx import ...` works
# regardless of where alembic is invoked from.
_HERE = os.path.dirname(os.path.abspath(__file__))          # backend/alembic/
_BACKEND_DIR = os.path.dirname(_HERE)                       # backend/
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)                  # repo root
for _p in (_REPO_ROOT, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.database import Base   # noqa: E402
import backend.models               # noqa: E402, F401 — registers all tables with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_sync_url() -> str:
    """
    Return a psycopg2-compatible URL for Alembic.

    The application uses asyncpg for the async FastAPI engine; Alembic requires
    a synchronous driver.  We swap the dialect prefix here so the same
    DATABASE_URL env var works for both.
    """
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Alembic cannot connect to the database."
        )
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)


def run_migrations_offline() -> None:
    context.configure(
        url=_get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_sync_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
