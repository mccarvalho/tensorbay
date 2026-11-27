"""Rate card (list price per GPU-hour), minimum order approval on opportunities

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
"""
import uuid

import sqlalchemy as sa
from alembic import op

revision = "e3f4a5b6c7d8"
down_revision = "d2e3f4a5b6c7"
branch_labels = None
depends_on = None

# platform, term (months), upfront %, US$ per GPU-hour. Orders of 32 servers (256 GPUs) or more.
RATES = [
    ("B300", 60, 35, "6.50"), ("B300", 60, 65, "6.22"), ("B300", 36, 35, "6.80"), ("B300", 36, 65, "6.44"),
    ("B200", 60, 35, "5.53"), ("B200", 60, 65, "5.29"), ("B200", 36, 35, "5.78"), ("B200", 36, 65, "5.47"),
    ("GB300", 60, 35, "7.20"), ("GB300", 60, 65, "6.89"), ("GB300", 36, 35, "8.80"), ("GB300", 36, 65, "8.33"),
    ("VR200", 60, 40, "10.00"), ("VR200", 36, 40, "11.00"),
]


def upgrade() -> None:
    table = op.create_table(
        "rate_card",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("platform", sa.String(16), nullable=False),
        sa.Column("term_months", sa.Integer, nullable=False),
        sa.Column("upfront_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("price_per_gpu_hour", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.UniqueConstraint("platform", "term_months", "upfront_pct", name="uq_rate_card_tier"),
    )
    op.create_index("ix_rate_card_platform", "rate_card", ["platform"])
    op.bulk_insert(table, [
        {"id": str(uuid.uuid4()), "platform": p, "term_months": t, "upfront_pct": u, "price_per_gpu_hour": pr,
         "created_by": "migration"} for p, t, u, pr in RATES
    ])
    op.add_column("opportunities", sa.Column("min_order_status", sa.String(10), nullable=True))
    op.add_column("opportunities", sa.Column("min_order_approved_by", sa.String(255), nullable=True))
    # Deals that already exist below the minimum are kept as they are (grandfathered).
    op.execute(
        "UPDATE opportunities SET min_order_status = 'APPROVED', min_order_approved_by = 'grandfathered' "
        "WHERE quantity < 256"
    )


def downgrade() -> None:
    op.drop_column("opportunities", "min_order_approved_by")
    op.drop_column("opportunities", "min_order_status")
    op.drop_table("rate_card")
