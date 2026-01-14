"""Add current_refresh_jti column for refresh token rotation

Revision ID: 20240117_000001
Revises: 20240116_000001
Create Date: 2024-01-17

This migration adds the current_refresh_jti column to track the unique ID
of the only valid refresh token for each user.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20240117_000001'
down_revision = '20240116_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add current_refresh_jti column."""
    # Add nullable column for the current valid refresh token JTI
    op.add_column('users', sa.Column('current_refresh_jti', sa.String(64), nullable=True))


def downgrade() -> None:
    """Remove current_refresh_jti column."""
    op.drop_column('users', 'current_refresh_jti')
