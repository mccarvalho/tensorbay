"""opportunities.node_spec: the one-line node description shared by a deal's documents

Revision ID: b0c1d2e3f4a5
Revises: a9b0c1d2e3f4
"""
import sqlalchemy as sa
from alembic import op

revision = "b0c1d2e3f4a5"
down_revision = "a9b0c1d2e3f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("node_spec", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "node_spec")
