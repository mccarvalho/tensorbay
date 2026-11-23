"""pipeline substages, hold, escrow flag and card fields

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
"""
import sqlalchemy as sa
from alembic import op

revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None

# old code -> new substage code
MAP = {
    "PROSPECTING": "NEW_LEAD",
    "QUALIFICATION": "INTRO_CALL",
    "PROPOSAL": "PROPOSAL_SENT",
    "NEGOTIATION": "UNDER_REVIEW",
    "DELIVERY": "PROVISIONING",
    "ACCEPTANCE": "ACCEPTANCE_TESTING",
}


def _remap(mapping: dict[str, str]) -> None:
    for old, new in mapping.items():
        op.execute(sa.text("UPDATE opportunities SET sales_stage = :new WHERE sales_stage = :old").bindparams(new=new, old=old))


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("stage_before_hold", sa.String(32), nullable=True))
    op.add_column("opportunities", sa.Column("region", sa.String(64), nullable=True))
    op.add_column("opportunities", sa.Column("assigned_to", sa.String(255), nullable=True))
    op.add_column("opportunities", sa.Column("next_action", sa.String(255), nullable=True))
    op.add_column(
        "opportunities",
        sa.Column("escrow_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    _remap(MAP)


def downgrade() -> None:
    _remap({new: old for old, new in MAP.items()})
    # Substages with no old equivalent fall back to the nearest old phase.
    _remap({
        "CONTACTED": "PROSPECTING", "KYC_SCREENING": "NEGOTIATION", "DOCS_SENT": "NEGOTIATION",
        "ESCROW_SETUP": "SIGNED", "AWAITING_DEPOSIT": "SIGNED", "ESCROW_FUNDED": "SIGNED",
        "READY_FOR_TESTING": "DELIVERY", "ACCEPTED": "ACCEPTANCE",
        "SUPPORT_SLA": "WON", "RENEWAL": "WON", "ON_HOLD": "PROSPECTING",
    })
    for c in ("escrow_required", "next_action", "assigned_to", "region", "stage_before_hold"):
        op.drop_column("opportunities", c)
