"""Add master_artwork_url and missing columns to products table.

Migration 001 created products with: id, category_id, nafdac_number, name,
manufacturer, description, is_approved, created_at, updated_at.

The Product ORM model defines additional columns that were never migrated.
This migration adds master_artwork_url (the column actively breaking queries)
plus the other missing columns to align the DB schema with the ORM model.

Revision ID: 003_add_master_artwork_url_to_products
Revises: 002_add_scan_details_and_gps
Create Date: 2026-03-22 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003_add_master_artwork_url'
down_revision = '002_add_scan_details_and_gps'
branch_labels = None
depends_on = None


def _col_exists(table: str, column: str) -> bool:
    """Return True if the column already exists (idempotent guard)."""
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
        ("company_id",          sa.UUID()),
        ("batch_number",        sa.String(100)),
        ("manufacturer_name",   sa.String(255)),
        ("manufacturing_date",  sa.Date()),
        ("expiry_date",         sa.Date()),
        ("ingredients",         sa.Text()),
        ("warnings",            sa.Text()),
        ("image_urls",          postgresql.JSONB()),
        ("master_artwork_url",  sa.Text()),
        ("status",              sa.String(50)),
        ("created_by",          sa.UUID()),
    ]

    for col_name, col_type in additions:
        if not _col_exists("products", col_name):
            op.add_column("products", sa.Column(col_name, col_type, nullable=True))

    # Add FK constraints only if the columns were just created
    bind = op.get_bind()
    fk_check = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_name = 'products' AND kcu.column_name = :c"
        ),
        {"c": "company_id"},
    )
    if fk_check.fetchone() is None:
        op.create_foreign_key(
            "fk_products_company_id", "products", "companies",
            ["company_id"], ["id"], ondelete="CASCADE"
        )

    fk_check2 = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "  AND tc.table_name = 'products' AND kcu.column_name = :c"
        ),
        {"c": "created_by"},
    )
    if fk_check2.fetchone() is None:
        op.create_foreign_key(
            "fk_products_created_by", "products", "users",
            ["created_by"], ["id"]
        )


def downgrade() -> None:
    op.drop_constraint("fk_products_created_by", "products", type_="foreignkey")
    op.drop_constraint("fk_products_company_id", "products", type_="foreignkey")
    for col_name in [
        "master_artwork_url", "image_urls", "warnings", "ingredients",
        "expiry_date", "manufacturing_date", "manufacturer_name",
        "batch_number", "company_id", "status", "created_by",
    ]:
        op.drop_column("products", col_name)
