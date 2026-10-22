"""add economics phase 3: commission_runs + commission_statements

Quarterly commission calculation: a run per (plan_year, quarter) and per-rep
statement lines carrying the annual-gate / true-up breakdown and payment status.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-22 09:05:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'commission_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('plan_year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('total_commission', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['plan_id'], ['commission_plans.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commission_runs_plan_year', 'commission_runs', ['plan_year'])

    op.create_table(
        'commission_statements',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('rep_id', sa.String(length=36), nullable=False),
        sa.Column('component', sa.String(length=8), nullable=False),
        sa.Column('plan_year', sa.Integer(), nullable=False),
        sa.Column('quarter', sa.Integer(), nullable=False),
        sa.Column('ytd_arr', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('quota_arr', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('gate_cleared', sa.Boolean(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('ytd_gross_profit', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('ytd_earned', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('prior_paid', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('payment_status', sa.String(length=8), nullable=False),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('payment_reference', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['commission_runs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['rep_id'], ['sales_reps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_commission_statements_run_id', 'commission_statements', ['run_id'])
    op.create_index('ix_commission_statements_rep_id', 'commission_statements', ['rep_id'])
    op.create_index('ix_commission_statements_plan_year', 'commission_statements', ['plan_year'])


def downgrade() -> None:
    op.drop_index('ix_commission_statements_plan_year', table_name='commission_statements')
    op.drop_index('ix_commission_statements_rep_id', table_name='commission_statements')
    op.drop_index('ix_commission_statements_run_id', table_name='commission_statements')
    op.drop_table('commission_statements')
    op.drop_index('ix_commission_runs_plan_year', table_name='commission_runs')
    op.drop_table('commission_runs')
