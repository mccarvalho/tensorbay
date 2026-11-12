"""add contacts.role

Job title / role of a customer contact (e.g. CTO, Procurement lead).

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-11-12 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'd0e1f2a3b4c5'
down_revision = 'c9d0e1f2a3b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('contacts', sa.Column('role', sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column('contacts', 'role')
