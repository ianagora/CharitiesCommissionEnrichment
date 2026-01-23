"""Add API key hash columns for secure storage

Revision ID: 20260123_000002
Revises: 20260123_000001
Create Date: 2026-01-23

This migration adds secure API key storage by:
1. Adding api_key_hash column for bcrypt-hashed API keys
2. Adding api_key_prefix column for efficient lookups
3. Removing the plain-text api_key column (after data migration)

SECURITY: API keys should never be stored in plain text.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260123_000002'
down_revision = '20260123_000001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new secure columns
    op.add_column('users', sa.Column('api_key_hash', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('api_key_prefix', sa.String(12), nullable=True))
    
    # Create index on api_key_prefix for efficient lookups
    op.create_index('ix_users_api_key_prefix', 'users', ['api_key_prefix'])
    
    # Note: If there are existing API keys, they need to be regenerated
    # since we cannot reverse-engineer the plain key from a hash.
    # Users with existing API keys will need to generate new ones.
    
    # Remove the old plain-text api_key column
    # First drop the index
    op.drop_index('ix_users_api_key', 'users')
    # Then drop the column
    op.drop_column('users', 'api_key')


def downgrade() -> None:
    # Re-add the old api_key column
    op.add_column('users', sa.Column('api_key', sa.String(64), nullable=True))
    op.create_index('ix_users_api_key', 'users', ['api_key'], unique=True)
    
    # Remove new columns
    op.drop_index('ix_users_api_key_prefix', 'users')
    op.drop_column('users', 'api_key_prefix')
    op.drop_column('users', 'api_key_hash')
