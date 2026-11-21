"""opportunities.short_name (names the deal's Drive folder YYYY-MM-<short name>)

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-11-21 18:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c5d6e7f8a9b0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('opportunities', sa.Column('short_name', sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column('opportunities', 'short_name')
