"""Node specs now come from the TensorBay spec sheets: drop the model-written lines saved before

Revision ID: c1d2e3f4a5b6
Revises: b0c1d2e3f4a5
"""
from alembic import op

revision = "c1d2e3f4a5b6"
down_revision = "b0c1d2e3f4a5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE opportunities SET node_spec = NULL")


def downgrade() -> None:
    pass
