"""Alembic configuration"""
import os
from alembic import config

alembic_cfg = config.Config("alembic.ini")
alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/sabilens"))
