"""add economics phase 2: commission_deals

Commissionable deals derived from won opportunities, with an approval workflow
(PENDING_APPROVAL -> APPROVED/REJECTED) and a persisted margin-warning flag.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-22 08:10:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'commission_deals',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('opportunity_id', sa.String(length=36), nullable=True),
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('plan_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('arr_type', sa.String(length=16), nullable=False),
        sa.Column('arr', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('margin_pct', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('gross_profit', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('ae_id', sa.String(length=36), nullable=True),
        sa.Column('am_id', sa.String(length=36), nullable=True),
        sa.Column('is_referred', sa.Boolean(), nullable=False),
        sa.Column('finder_id', sa.String(length=36), nullable=True),
        sa.Column('booked_date', sa.Date(), nullable=False),
        sa.Column('plan_year', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('margin_warning', sa.Boolean(), nullable=False),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['commission_plans.id']),
        sa.ForeignKeyConstraint(['ae_id'], ['sales_reps.id']),
        sa.ForeignKeyConstraint(['am_id'], ['sales_reps.id']),
        sa.ForeignKeyConstraint(['finder_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commission_deals_opportunity_id', 'commission_deals', ['opportunity_id'])
    op.create_index('ix_commission_deals_customer_id', 'commission_deals', ['customer_id'])
    op.create_index('ix_commission_deals_plan_id', 'commission_deals', ['plan_id'])
    op.create_index('ix_commission_deals_ae_id', 'commission_deals', ['ae_id'])
    op.create_index('ix_commission_deals_am_id', 'commission_deals', ['am_id'])
    op.create_index('ix_commission_deals_finder_id', 'commission_deals', ['finder_id'])
    op.create_index('ix_commission_deals_plan_year', 'commission_deals', ['plan_year'])
    op.create_index('ix_commission_deals_status', 'commission_deals', ['status'])


def downgrade() -> None:
    for idx in (
        'ix_commission_deals_status',
        'ix_commission_deals_plan_year',
        'ix_commission_deals_finder_id',
        'ix_commission_deals_am_id',
        'ix_commission_deals_ae_id',
        'ix_commission_deals_plan_id',
        'ix_commission_deals_customer_id',
        'ix_commission_deals_opportunity_id',
    ):
        op.drop_index(idx, table_name='commission_deals')
    op.drop_table('commission_deals')
