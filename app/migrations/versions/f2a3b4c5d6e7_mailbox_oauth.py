"""mailbox OAuth connection (encrypted refresh token)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-11-12 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mail_mailboxes', sa.Column('refresh_token_enc', sa.Text(), nullable=True))
    op.add_column('mail_mailboxes', sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('mail_mailboxes', sa.Column('connected_by', sa.String(length=320), nullable=True))
    op.add_column(
        'mail_mailboxes',
        sa.Column('needs_reconnect', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('mail_mailboxes', 'needs_reconnect')
    op.drop_column('mail_mailboxes', 'connected_by')
    op.drop_column('mail_mailboxes', 'connected_at')
    op.drop_column('mail_mailboxes', 'refresh_token_enc')
