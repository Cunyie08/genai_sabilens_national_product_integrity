"""Initial schema creation

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-03-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables"""
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('email', sa.String(), unique=True, nullable=False),
        sa.Column('phone', sa.String(), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('first_name', sa.String(), nullable=True),
        sa.Column('last_name', sa.String(), nullable=True),
        sa.Column('role', sa.String(), nullable=False, default='consumer'),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('phone_verified', sa.Boolean(), default=False),
        sa.Column('email_verified', sa.Boolean(), default=False),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )
    
    # OTP Verification table
    op.create_table(
        'otp_verifications',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('phone', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('otp_code', sa.String(6), nullable=False),
        sa.Column('purpose', sa.String(), nullable=False),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Sessions table
    op.create_table(
        'sessions',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('refresh_token', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Scans table
    op.create_table(
        'scans',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('product_id', sa.UUID(), nullable=True),
        sa.Column('image_url', sa.String(), nullable=True),
        sa.Column('barcode', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('location_text', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    
    # Scan Analysis table
    op.create_table(
        'scan_analyses',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('scan_id', sa.UUID(), nullable=False),
        sa.Column('confidence_score', sa.Float(), default=0.0),
        sa.Column('visual_analysis', sa.JSON(), nullable=True),
        sa.Column('ocr_analysis', sa.JSON(), nullable=True),
        sa.Column('regulatory_check', sa.JSON(), nullable=True),
        sa.Column('fusion_result', sa.JSON(), nullable=True),
        sa.Column('risk_level', sa.String(), nullable=True),
        sa.Column('recommendation', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['scan_id'], ['scans.id'], ondelete='CASCADE'),
    )
    
    # Products table
    op.create_table(
        'products',
        sa.Column('id', sa.UUID(), nullable=False, primary_key=True),
        sa.Column('category_id', sa.UUID(), nullable=True),
        sa.Column('nafdac_number', sa.String(), nullable=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('manufacturer', sa.String(), nullable=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('is_approved', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Drop all tables"""
    op.drop_table('scan_analyses')
    op.drop_table('scans')
    op.drop_table('sessions')
    op.drop_table('otp_verifications')
    op.drop_table('products')
    op.drop_table('users')
