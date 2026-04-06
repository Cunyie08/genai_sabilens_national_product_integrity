"""Add data_requests table for NAFDAC gated access flow

Revision ID: 005_add_data_requests
Revises: 004_ensure_scan_image_columns
Create Date: 2026-04-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = '005_add_data_requests'
down_revision = '004_ensure_scan_image_columns'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table( 
        'data_requests',
        sa.Column('id',          UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id',     UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('endpoint',    sa.String(100),  nullable=False),
        sa.Column('purpose',     sa.Text(),       nullable=False),
        sa.Column('status',      sa.String(20),   nullable=False, server_default='pending'),
        # status IN ('pending', 'approved', 'denied')
        sa.Column('review_note', sa.Text(),       nullable=True),
        sa.Column('reviewed_by', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at',  sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at',  sa.DateTime(timezone=True), server_default=sa.text('NOW()')),
    )

    # Index for fast lookup of a user's approved requests on a given endpoint
    op.create_index(
        'ix_data_requests_user_endpoint_status',
        'data_requests',
        ['user_id', 'endpoint', 'status'],
    )

    # Index for admin review queue — pending requests ordered by created_at
    op.create_index(
        'ix_data_requests_status_created',
        'data_requests',
        ['status', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_data_requests_status_created',       table_name='data_requests')
    op.drop_index('ix_data_requests_user_endpoint_status', table_name='data_requests')
    op.drop_table('data_requests')
