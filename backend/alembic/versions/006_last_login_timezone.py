"""Convert last_login to TIMESTAMP WITH TIME ZONE

Revision ID: 006_last_login_timezone
Revises: 005_add_data_requests
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = '006_last_login_timezone'
down_revision = '005_add_data_requests'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'users', 'last_login',
        type_=sa.DateTime(timezone=True),
        postgresql_using="last_login AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.alter_column(
        'users', 'last_login',
        type_=sa.DateTime(timezone=False)
    )
