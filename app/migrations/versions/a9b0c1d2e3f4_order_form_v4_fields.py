"""Order Form V4 fields on opportunities: upfront %, payment structure, delivery targets

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
"""
import sqlalchemy as sa
from alembic import op

revision = "a9b0c1d2e3f4"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("upfront_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("opportunities", sa.Column("payment_structure", sa.String(1), nullable=True))
    op.add_column("opportunities", sa.Column("first_delivery_date", sa.Date(), nullable=True))
    op.add_column("opportunities", sa.Column("latest_delivery_date", sa.Date(), nullable=True))


def downgrade() -> None:
    for c in ("latest_delivery_date", "first_delivery_date", "payment_structure", "upfront_pct"):
        op.drop_column("opportunities", c)
