"""add economics phase 1: sales_reps + commission_plans

Foundation for the Economics & Commissions domain (TensorBay Commission Plan
FY2026): a registry of sales reps/finders and a versioned commission plan
carrying rates, quota gates and the default margin.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-22 07:55:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sales_reps',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('type', sa.String(length=8), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('base_salary', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('cognito_sub', sa.String(length=64), nullable=True),
        sa.Column('payment_details', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sales_reps_name', 'sales_reps', ['name'])
    op.create_index('ix_sales_reps_email', 'sales_reps', ['email'])
    op.create_index('ix_sales_reps_cognito_sub', 'sales_reps', ['cognito_sub'])

    op.create_table(
        'commission_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('plan_year', sa.Integer(), nullable=False),
        sa.Column('ae_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('am_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('finder_rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('ae_quota_arr', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('am_quota_arr', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('default_margin_pct', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commission_plans_plan_year', 'commission_plans', ['plan_year'])


def downgrade() -> None:
    op.drop_index('ix_commission_plans_plan_year', table_name='commission_plans')
    op.drop_table('commission_plans')
    op.drop_index('ix_sales_reps_cognito_sub', table_name='sales_reps')
    op.drop_index('ix_sales_reps_email', table_name='sales_reps')
    op.drop_index('ix_sales_reps_name', table_name='sales_reps')
    op.drop_table('sales_reps')
