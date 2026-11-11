"""add sales_reps.lead_eligible

Who receives inbound leads is now driven by the portal role (SALES /
SALES_MANAGER users are synced to a rep) instead of the rep ``type``. Existing
active Account Managers keep receiving leads.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-11 09:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c9d0e1f2a3b4'
down_revision = 'b8c9d0e1f2a3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'sales_reps',
        sa.Column('lead_eligible', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE sales_reps SET lead_eligible = TRUE WHERE type = 'AM'")


def downgrade() -> None:
    op.drop_column('sales_reps', 'lead_eligible')
