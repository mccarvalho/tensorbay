"""add economics phase 4: cost_items

Total-cost tracking (GPU acquisition, colocation, etc.) allocatable to a
customer and/or commission deal for real-margin computation.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-22 10:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cost_items',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=24), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('period', sa.String(length=16), nullable=False),
        sa.Column('incurred_on', sa.Date(), nullable=True),
        sa.Column('customer_id', sa.String(length=36), nullable=True),
        sa.Column('deal_id', sa.String(length=36), nullable=True),
        sa.Column('supplier_id', sa.String(length=36), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['deal_id'], ['commission_deals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cost_items_name', 'cost_items', ['name'])
    op.create_index('ix_cost_items_category', 'cost_items', ['category'])
    op.create_index('ix_cost_items_customer_id', 'cost_items', ['customer_id'])
    op.create_index('ix_cost_items_deal_id', 'cost_items', ['deal_id'])


def downgrade() -> None:
    op.drop_index('ix_cost_items_deal_id', table_name='cost_items')
    op.drop_index('ix_cost_items_customer_id', table_name='cost_items')
    op.drop_index('ix_cost_items_category', table_name='cost_items')
    op.drop_index('ix_cost_items_name', table_name='cost_items')
    op.drop_table('cost_items')
