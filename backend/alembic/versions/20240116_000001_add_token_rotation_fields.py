"""Add token rotation fields to users table.

Revision ID: 20240116_000001
Revises: 20240115_000000
Create Date: 2024-01-16 00:00:01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20240116_000001'
down_revision: Union[str, None] = '20240115_000000'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add token_version and refresh_token_family columns to users table."""
    # Add token_version column with default 0
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='0')
    )
    
    # Add refresh_token_family column for tracking token rotation
    op.add_column(
        'users',
        sa.Column('refresh_token_family', sa.String(64), nullable=True)
    )
    
    # Create index on refresh_token_family for efficient lookup
    op.create_index(
        'ix_users_refresh_token_family',
        'users',
        ['refresh_token_family'],
        unique=False
    )


def downgrade() -> None:
    """Remove token rotation fields from users table."""
    op.drop_index('ix_users_refresh_token_family', table_name='users')
    op.drop_column('users', 'refresh_token_family')
    op.drop_column('users', 'token_version')
