"""order form intake links

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
"""
import sqlalchemy as sa
from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_form_intakes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("opportunity_id", sa.String(36), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_enc", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_order_form_intakes_opportunity_id", "order_form_intakes", ["opportunity_id"])
    op.create_index("ix_order_form_intakes_token_hash", "order_form_intakes", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_order_form_intakes_token_hash", table_name="order_form_intakes")
    op.drop_index("ix_order_form_intakes_opportunity_id", table_name="order_form_intakes")
    op.drop_table("order_form_intakes")
