"""google drive storage for generated documents

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-11-21 15:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'b4c5d6e7f8a9'
down_revision = 'a3b4c5d6e7f8'
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
    op.create_table(
        'drive_connections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('account_email', sa.String(length=320), nullable=False),
        sa.Column('refresh_token_enc', sa.Text(), nullable=True),
        sa.Column('connected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('connected_by', sa.String(length=320), nullable=True),
        sa.Column('needs_reconnect', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('root_folder_id', sa.String(length=128), nullable=True),
        sa.Column('root_folder_name', sa.String(length=512), nullable=True),
        sa.Column('root_folder_url', sa.String(length=1024), nullable=True),
        *_audit(),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'drive_folders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('root_folder_id', sa.String(length=128), nullable=False),
        sa.Column('path', sa.String(length=1024), nullable=False),
        sa.Column('folder_id', sa.String(length=128), nullable=False),
        *_audit(),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_drive_folders_root_folder_id', 'drive_folders', ['root_folder_id'])


def downgrade() -> None:
    op.drop_table('drive_folders')
    op.drop_table('drive_connections')
