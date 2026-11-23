"""deal documents: versions, DOCX key, Drive link

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
"""
import sqlalchemy as sa
from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None

COLS = [
    ("opportunity_id", sa.String(36)), ("file_name", sa.String(255)), ("docx_s3_key", sa.String(1024)),
    ("notes", sa.Text()), ("error", sa.Text()), ("drive_file_id", sa.String(128)),
    ("drive_url", sa.String(1024)), ("drive_error", sa.Text()),
]


def upgrade() -> None:
    for name, typ in COLS:
        op.add_column("generated_documents", sa.Column(name, typ, nullable=True))
    op.add_column("generated_documents", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_generated_documents_opportunity_id", "generated_documents", ["opportunity_id"])


def downgrade() -> None:
    op.drop_index("ix_generated_documents_opportunity_id", table_name="generated_documents")
    op.drop_column("generated_documents", "version")
    for name, _ in reversed(COLS):
        op.drop_column("generated_documents", name)
