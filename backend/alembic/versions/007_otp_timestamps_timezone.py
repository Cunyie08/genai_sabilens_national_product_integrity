"""Convert otp_verifications expires_at and verified_at to TIMESTAMP WITH TIME ZONE

Revision ID: 007_otp_timestamps_timezone
Revises: 006_last_login_timezone
Create Date: 2026-04-27
"""

from alembic import op
import sqlalchemy as sa

revision = '007_otp_timestamps_timezone'
down_revision = '006_last_login_timezone'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'otp_verifications', 'expires_at',
        type_=sa.DateTime(timezone=True),
        postgresql_using="expires_at AT TIME ZONE 'UTC'"
    )
    op.alter_column(
        'otp_verifications', 'verified_at',
        type_=sa.DateTime(timezone=True),
        postgresql_using="verified_at AT TIME ZONE 'UTC'"
    )


def downgrade() -> None:
    op.alter_column(
        'otp_verifications', 'expires_at',
        type_=sa.DateTime(timezone=False)
    )
    op.alter_column(
        'otp_verifications', 'verified_at',
        type_=sa.DateTime(timezone=False)
    )
