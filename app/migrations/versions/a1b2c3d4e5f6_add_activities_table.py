"""add activities table (CRM touchpoints)

Revision ID: a1b2c3d4e5f6
Revises: 5942f3ab7e03
Create Date: 2026-10-17 19:45:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '5942f3ab7e03'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'activities',
        sa.Column('customer_id', sa.String(length=36), nullable=False),
        sa.Column('contact_id', sa.String(length=36), nullable=True),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(length=255), nullable=True),
        sa.Column(
            'occurred_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column('next_follow_up_date', sa.Date(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('(CURRENT_TIMESTAMP)'),
            nullable=False,
        ),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['contact_id'], ['contacts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_activities_customer_id'), 'activities', ['customer_id'], unique=False
    )
    op.create_index(
        op.f('ix_activities_occurred_at'), 'activities', ['occurred_at'], unique=False
    )
    op.create_index(
        op.f('ix_activities_next_follow_up_date'),
        'activities',
        ['next_follow_up_date'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_activities_next_follow_up_date'), table_name='activities')
    op.drop_index(op.f('ix_activities_occurred_at'), table_name='activities')
    op.drop_index(op.f('ix_activities_customer_id'), table_name='activities')
    op.drop_table('activities')
