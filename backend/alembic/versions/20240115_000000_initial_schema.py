"""Initial database schema

Revision ID: 20240115_000000
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision: str = '20240115_000000'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    conn = op.get_bind()
    inspector = inspect(conn)
    return table_name in inspector.get_table_names()


def upgrade() -> None:
    # Create users table only if it doesn't exist
    if not table_exists('users'):
        op.create_table(
            'users',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('email', sa.String(255), nullable=False),
            sa.Column('hashed_password', sa.String(255), nullable=False),
            sa.Column('full_name', sa.String(255), nullable=True),
            sa.Column('organization', sa.String(255), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, default=True),
            sa.Column('is_superuser', sa.Boolean(), nullable=False, default=False),
            sa.Column('is_verified', sa.Boolean(), nullable=False, default=False),
            sa.Column('api_key', sa.String(64), nullable=True),
            sa.Column('api_key_created_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('last_login_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Create batches table only if it doesn't exist
    if not table_exists('batches'):
        op.create_table(
            'batches',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('filename', sa.String(255), nullable=False),
            sa.Column('total_records', sa.Integer(), nullable=False),
            sa.Column('processed_records', sa.Integer(), nullable=False, default=0),
            sa.Column('status', sa.String(50), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('completed_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )

    # Create charities table only if it doesn't exist
    if not table_exists('charities'):
        op.create_table(
            'charities',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('charity_number', sa.String(50), nullable=False),
            sa.Column('charity_name', sa.String(255), nullable=True),
            sa.Column('registration_date', sa.Date(), nullable=True),
            sa.Column('removal_date', sa.Date(), nullable=True),
            sa.Column('status', sa.String(50), nullable=True),
            sa.Column('income', sa.Numeric(), nullable=True),
            sa.Column('spending', sa.Numeric(), nullable=True),
            sa.Column('activities', sa.Text(), nullable=True),
            sa.Column('contact_info', sa.JSON(), nullable=True),
            sa.Column('trustees', sa.JSON(), nullable=True),
            sa.Column('enriched_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['batch_id'], ['batches.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_charities_charity_number', 'charities', ['charity_number'])

    # Create audit_logs table only if it doesn't exist
    if not table_exists('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('action', sa.String(100), nullable=False),
            sa.Column('resource_type', sa.String(100), nullable=True),
            sa.Column('resource_id', sa.String(255), nullable=True),
            sa.Column('ip_address', sa.String(45), nullable=True),
            sa.Column('user_agent', sa.String(500), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('charities')
    op.drop_table('batches')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
