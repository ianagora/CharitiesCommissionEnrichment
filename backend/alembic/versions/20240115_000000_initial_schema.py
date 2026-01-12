"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
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
    op.create_index('ix_users_api_key', 'users', ['api_key'], unique=True)

    # Create entity_batches table
    op.create_table(
        'entity_batches',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('original_filename', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('uploaded', 'processing', 'completed', 'failed', 'partial', name='batchstatus'), nullable=False, default='uploaded'),
        sa.Column('total_records', sa.Integer(), nullable=False, default=0),
        sa.Column('processed_records', sa.Integer(), nullable=False, default=0),
        sa.Column('matched_records', sa.Integer(), nullable=False, default=0),
        sa.Column('failed_records', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processing_started_at', sa.DateTime(), nullable=True),
        sa.Column('processing_completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create entities table
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('batch_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('original_name', sa.String(500), nullable=False),
        sa.Column('original_data', postgresql.JSON(), nullable=True),
        sa.Column('row_number', sa.Integer(), nullable=True),
        sa.Column('entity_type', sa.Enum('charity', 'company', 'trust', 'cio', 'unknown', name='entitytype'), nullable=False, default='unknown'),
        sa.Column('resolved_name', sa.String(500), nullable=True),
        sa.Column('charity_number', sa.String(50), nullable=True),
        sa.Column('company_number', sa.String(50), nullable=True),
        sa.Column('charity_status', sa.String(100), nullable=True),
        sa.Column('charity_registration_date', sa.DateTime(), nullable=True),
        sa.Column('charity_removal_date', sa.DateTime(), nullable=True),
        sa.Column('charity_activities', sa.Text(), nullable=True),
        sa.Column('charity_contact_email', sa.String(255), nullable=True),
        sa.Column('charity_contact_phone', sa.String(50), nullable=True),
        sa.Column('charity_website', sa.String(500), nullable=True),
        sa.Column('charity_address', sa.Text(), nullable=True),
        sa.Column('latest_income', sa.Float(), nullable=True),
        sa.Column('latest_expenditure', sa.Float(), nullable=True),
        sa.Column('latest_financial_year_end', sa.DateTime(), nullable=True),
        sa.Column('resolution_status', sa.Enum('pending', 'matched', 'multiple_matches', 'no_match', 'manual_review', 'confirmed', 'rejected', name='resolutionstatus'), nullable=False, default='pending'),
        sa.Column('resolution_confidence', sa.Float(), nullable=True),
        sa.Column('resolution_method', sa.String(50), nullable=True),
        sa.Column('parent_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ownership_level', sa.Integer(), nullable=False, default=0),
        sa.Column('enriched_data', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['batch_id'], ['entity_batches.id'], ),
        sa.ForeignKeyConstraint(['parent_entity_id'], ['entities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_entities_charity_number', 'entities', ['charity_number'])
    op.create_index('ix_entities_company_number', 'entities', ['company_number'])

    # Create entity_resolutions table
    op.create_table(
        'entity_resolutions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('charity_number', sa.String(50), nullable=True),
        sa.Column('company_number', sa.String(50), nullable=True),
        sa.Column('candidate_name', sa.String(500), nullable=False),
        sa.Column('candidate_data', postgresql.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('match_method', sa.String(50), nullable=False),
        sa.Column('is_selected', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create entity_ownerships table
    op.create_table(
        'entity_ownerships',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('owned_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ownership_type', sa.String(100), nullable=True),
        sa.Column('ownership_percentage', sa.Float(), nullable=True),
        sa.Column('relationship_description', sa.Text(), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('verified', sa.Boolean(), nullable=False, default=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['owner_id'], ['entities.id'], ),
        sa.ForeignKeyConstraint(['owned_id'], ['entities.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.Enum('login', 'logout', 'batch_upload', 'batch_process', 'entity_resolve', 'entity_confirm', 'entity_reject', 'ownership_build', 'export', 'api_call', 'error', name='auditaction'), nullable=False),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('endpoint', sa.String(255), nullable=True),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('success', sa.String(10), nullable=False, default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('entity_ownerships')
    op.drop_table('entity_resolutions')
    op.drop_table('entities')
    op.drop_table('entity_batches')
    op.drop_table('users')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS auditaction')
    op.execute('DROP TYPE IF EXISTS resolutionstatus')
    op.execute('DROP TYPE IF EXISTS entitytype')
    op.execute('DROP TYPE IF EXISTS batchstatus')
