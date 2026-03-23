"""Ensure all scan image/data columns exist in the scans table.

Migration 001 was supposed to create image_url as part of CREATE TABLE scans,
but the live DB was provisioned without it (or from a different schema revision).
Migration 002 added back_image_url, scan_image_urls, and scan_data but did not
guard image_url.  This migration adds all four columns idempotently.

Revision ID: 004_ensure_scan_image_columns
Revises: 003_add_master_artwork_url
Create Date: 2026-03-23 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_ensure_scan_image_columns'
down_revision = '003_add_master_artwork_url'
branch_labels = None
depends_on = None


def _col_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    additions = [
        ("image_url",       sa.String()),
        ("back_image_url",  sa.String()),
        ("scan_image_urls", postgresql.JSONB()),
        ("scan_data",       postgresql.JSONB()),
    ]
    for col_name, col_type in additions:
        if not _col_exists("scans", col_name):
            op.add_column("scans", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    # Only drop columns that this migration is solely responsible for adding.
    # back_image_url, scan_image_urls, scan_data are owned by migration 002;
    # image_url is owned by migration 001 — we only touch them here as a fix,
    # so downgrade is a no-op to avoid breaking the earlier migrations' state.
    pass
