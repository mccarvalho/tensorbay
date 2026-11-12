"""email sync: mailboxes, unmatched inbox, activity capture columns

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-11-12 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'e1f2a3b4c5d6'
down_revision = 'd0e1f2a3b4c5'
branch_labels = None
depends_on = None


def _audit() -> list:
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
    ]


def upgrade() -> None:
    op.add_column('activities', sa.Column('source', sa.String(length=32), nullable=True))
    op.add_column('activities', sa.Column('direction', sa.String(length=8), nullable=True))
    op.add_column('activities', sa.Column('external_id', sa.String(length=255), nullable=True))
    op.create_unique_constraint(
        'uq_activity_customer_external', 'activities', ['customer_id', 'external_id']
    )

    op.create_table(
        'mail_mailboxes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('address', sa.String(length=320), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('capture_unmatched', sa.Boolean(), nullable=False),
        sa.Column('history_id', sa.String(length=64), nullable=True),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_logged', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_logged', sa.Integer(), nullable=False, server_default='0'),
        *_audit(),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mail_mailboxes_address', 'mail_mailboxes', ['address'], unique=True)

    op.create_table(
        'mail_unmatched',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('mailbox', sa.String(length=320), nullable=False),
        sa.Column('message_id', sa.String(length=255), nullable=False),
        sa.Column('direction', sa.String(length=8), nullable=False),
        sa.Column('from_addr', sa.String(length=320), nullable=False),
        sa.Column('external_addrs', sa.Text(), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('resolved_customer_id', sa.String(length=36), nullable=True),
        *_audit(),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mail_unmatched_message_id', 'mail_unmatched', ['message_id'], unique=True)
    op.create_index('ix_mail_unmatched_sent_at', 'mail_unmatched', ['sent_at'])
    op.create_index('ix_mail_unmatched_status', 'mail_unmatched', ['status'])


def downgrade() -> None:
    op.drop_table('mail_unmatched')
    op.drop_table('mail_mailboxes')
    op.drop_constraint('uq_activity_customer_external', 'activities', type_='unique')
    op.drop_column('activities', 'external_id')
    op.drop_column('activities', 'direction')
    op.drop_column('activities', 'source')
