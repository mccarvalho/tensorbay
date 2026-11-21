"""supply orders (GPU purchase contracts by totals) + delivery lots

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-11-21 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'capacity_supply_orders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('reference', sa.String(length=128), nullable=False),
        sa.Column('supplier_id', sa.String(length=36), nullable=True),
        sa.Column('supplier_quote', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('signed_on', sa.Date(), nullable=True),
        sa.Column('gpu_model', sa.String(length=64), nullable=False),
        sa.Column('server_model', sa.String(length=128), nullable=True),
        sa.Column('gpus_per_server', sa.Integer(), nullable=False),
        sa.Column('servers', sa.Integer(), nullable=False),
        sa.Column('gpus_total', sa.Integer(), nullable=False),
        sa.Column('unit_price_per_server', sa.Numeric(18, 2), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=True),
        sa.Column('total_value', sa.Numeric(20, 2), nullable=True),
        sa.Column('payment_terms', sa.Text(), nullable=True),
        sa.Column('assembly_site', sa.String(length=255), nullable=True),
        sa.Column('destination_site', sa.String(length=255), nullable=True),
        sa.Column('tax_regime', sa.String(length=255), nullable=True),
        sa.Column('delivery_window', sa.String(length=128), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_capacity_supply_orders_supplier_id', 'capacity_supply_orders', ['supplier_id'])
    op.create_index('ix_capacity_supply_orders_status', 'capacity_supply_orders', ['status'])
    op.create_index('ix_capacity_supply_orders_gpu_model', 'capacity_supply_orders', ['gpu_model'])

    op.add_column('capacity_incoming', sa.Column('order_id', sa.String(length=36), nullable=True))
    op.add_column('capacity_incoming', sa.Column('lot_label', sa.String(length=64), nullable=True))
    op.create_index('ix_capacity_incoming_order_id', 'capacity_incoming', ['order_id'])
    op.create_foreign_key(
        'fk_capacity_incoming_order', 'capacity_incoming', 'capacity_supply_orders',
        ['order_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_capacity_incoming_order', 'capacity_incoming', type_='foreignkey')
    op.drop_index('ix_capacity_incoming_order_id', table_name='capacity_incoming')
    op.drop_column('capacity_incoming', 'lot_label')
    op.drop_column('capacity_incoming', 'order_id')
    op.drop_table('capacity_supply_orders')
