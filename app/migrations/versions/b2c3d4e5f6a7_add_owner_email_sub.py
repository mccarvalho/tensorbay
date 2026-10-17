"""add account_owner_email and account_owner_sub to opportunities

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-17 20:55:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'opportunities',
        sa.Column('account_owner_email', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'opportunities',
        sa.Column('account_owner_sub', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('opportunities', 'account_owner_sub')
    op.drop_column('opportunities', 'account_owner_email')
