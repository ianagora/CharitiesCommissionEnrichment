"""add 2fa fields

Revision ID: 20260123_000001
Revises: 20240117_000001
Create Date: 2026-01-23 12:55:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260123_000001'
down_revision = '20240117_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add 2FA columns
    op.add_column('users', sa.Column('two_factor_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('two_factor_secret', sa.String(32), nullable=True))
    op.add_column('users', sa.Column('backup_codes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'backup_codes')
    op.drop_column('users', 'two_factor_secret')
    op.drop_column('users', 'two_factor_enabled')
