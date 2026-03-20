"""Add scan detail columns and GPS float fields to scans table.

Migration 001 created scans with: id, user_id, product_id, image_url, barcode,
latitude (Float), longitude (Float), location_text, status, created_at, updated_at.

This migration adds the AI-result and product-detail columns that the Scan model
uses but were not present in the initial schema.

Revision ID: 002_add_scan_details_and_gps
Revises: 001_initial_schema
Create Date: 2026-03-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002_add_scan_details_and_gps'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def _col_exists(table: str, column: str) -> bool:
    """Return True if the column already exists (idempotent guard)."""
    from alembic import op as _op
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
    """Add product detail + AI result columns to scans; GPS float cols already exist."""

    additions = [
        # Product detail columns
        ("product_name",    sa.String(255)),
        ("category",        sa.String(100)),
        ("manufacturer",    sa.String(255)),
        ("nafdac_number",   sa.String(100)),
        ("batch_number",    sa.String(100)),
        ("expiry_date",     sa.Date()),
        # AI scoring
        ("confidence_score", sa.Numeric(5, 4)),
        ("similarity_score", sa.Numeric(5, 2)),
        # Images
        ("back_image_url",  sa.String()),
        ("scan_image_urls", postgresql.JSONB()),
        # Full AI payload
        ("scan_data",       postgresql.JSONB()),
    ]

    for col_name, col_type in additions:
        if not _col_exists("scans", col_name):
            op.add_column("scans", sa.Column(col_name, col_type, nullable=True))

    # Ensure GPS float columns exist (they should from migration 001, but guard anyway)
    for col_name, col_type in [("latitude", sa.Float()), ("longitude", sa.Float()), ("location_text", sa.String())]:
        if not _col_exists("scans", col_name):
            op.add_column("scans", sa.Column(col_name, col_type, nullable=True))


def downgrade() -> None:
    for col_name in [
        "scan_data", "scan_image_urls", "back_image_url",
        "similarity_score", "confidence_score", "expiry_date",
        "batch_number", "nafdac_number", "manufacturer", "category", "product_name",
    ]:
        op.drop_column("scans", col_name)
