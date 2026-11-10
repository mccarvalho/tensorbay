"""add leads + sales_reps.regions

Inbound website lead inbox (routed to Account Managers by region) and the
per-rep ``regions`` list used for that routing.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-10 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b8c9d0e1f2a3'
down_revision = 'a7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('sales_reps', sa.Column('regions', sa.String(length=255), nullable=True))

    op.create_table(
        'leads',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('submission_id', sa.String(length=128), nullable=False),
        sa.Column('source', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('sku_of_interest', sa.String(length=255), nullable=True),
        sa.Column('gpu_count', sa.Integer(), nullable=True),
        sa.Column('pricing_model_or_term', sa.String(length=255), nullable=True),
        sa.Column('site_language', sa.String(length=16), nullable=True),
        sa.Column('region', sa.String(length=128), nullable=True),
        sa.Column('country', sa.String(length=128), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('page_url', sa.String(length=1024), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('assigned_rep_id', sa.String(length=36), nullable=True),
        sa.Column('needs_review', sa.Boolean(), nullable=False),
        sa.Column('duplicate_of_id', sa.String(length=36), nullable=True),
        sa.Column('disqualified_reason', sa.String(length=1024), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('converted_customer_id', sa.String(length=36), nullable=True),
        sa.Column('converted_opportunity_id', sa.String(length=36), nullable=True),
        sa.Column('raw_payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['assigned_rep_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_leads_submission_id', 'leads', ['submission_id'], unique=True)
    op.create_index('ix_leads_email', 'leads', ['email'])
    op.create_index('ix_leads_region', 'leads', ['region'])
    op.create_index('ix_leads_status', 'leads', ['status'])
    op.create_index('ix_leads_assigned_rep_id', 'leads', ['assigned_rep_id'])


def downgrade() -> None:
    for idx in (
        'ix_leads_assigned_rep_id',
        'ix_leads_status',
        'ix_leads_region',
        'ix_leads_email',
        'ix_leads_submission_id',
    ):
        op.drop_index(idx, table_name='leads')
    op.drop_table('leads')
    op.drop_column('sales_reps', 'regions')
