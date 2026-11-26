"""capacity_availability: the sales-facing list of what can be offered now and by month

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
"""
import sqlalchemy as sa
from alembic import op

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capacity_availability",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("gpu_model", sa.String(64), nullable=False),
        sa.Column("cooling", sa.String(8), nullable=True),
        sa.Column("quantity_unit", sa.String(8), nullable=False, server_default="GPUS"),
        sa.Column("site", sa.String(255), nullable=False),
        sa.Column("available_from", sa.Date, nullable=True),
        sa.Column("total_qty", sa.Integer, nullable=True),
        sa.Column("available_qty", sa.Integer, nullable=False),
        sa.Column("price_per_gpu_hour", sa.Numeric(12, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )
    op.create_index("ix_capacity_availability_gpu_model", "capacity_availability", ["gpu_model"])
    op.create_index("ix_capacity_availability_available_from", "capacity_availability", ["available_from"])


def downgrade() -> None:
    op.drop_table("capacity_availability")
