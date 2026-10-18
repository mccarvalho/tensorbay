"""add suppliers + supplier_contacts, link capacity_incoming to suppliers

Adds first-class Supplier/Distributor entities and extends incoming capacity
with a supplier FK, procurement status, pricing, and estimated/actual dates.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-18 06:20:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'suppliers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('legal_name', sa.String(length=255), nullable=True),
        sa.Column('tier', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('account_manager', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_suppliers_name', 'suppliers', ['name'])

    op.create_table(
        'supplier_contacts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('supplier_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=128), nullable=True),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('phone', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('updated_by', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['supplier_id'], ['suppliers.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_supplier_contacts_supplier_id', 'supplier_contacts', ['supplier_id']
    )

    # Extend incoming capacity
    op.add_column(
        'capacity_incoming',
        sa.Column('supplier_id', sa.String(length=36), nullable=True),
    )
    op.add_column(
        'capacity_incoming',
        sa.Column(
            'status',
            sa.String(length=16),
            nullable=False,
            server_default='NEGOTIATING',
        ),
    )
    op.add_column(
        'capacity_incoming',
        sa.Column('unit_price', sa.Numeric(precision=18, scale=2), nullable=True),
    )
    op.add_column(
        'capacity_incoming',
        sa.Column('currency', sa.String(length=3), nullable=True),
    )
    op.add_column(
        'capacity_incoming',
        sa.Column('actual_delivery', sa.Date(), nullable=True),
    )
    op.add_column(
        'capacity_incoming',
        sa.Column('actual_operational', sa.Date(), nullable=True),
    )
    op.create_index(
        'ix_capacity_incoming_supplier_id', 'capacity_incoming', ['supplier_id']
    )
    op.create_index(
        'ix_capacity_incoming_status', 'capacity_incoming', ['status']
    )
    op.create_foreign_key(
        'fk_capacity_incoming_supplier_id',
        'capacity_incoming',
        'suppliers',
        ['supplier_id'],
        ['id'],
    )
    # Drop the server_default now that existing rows are backfilled; the ORM
    # supplies the default going forward.
    op.alter_column('capacity_incoming', 'status', server_default=None)


def downgrade() -> None:
    op.drop_constraint(
        'fk_capacity_incoming_supplier_id', 'capacity_incoming', type_='foreignkey'
    )
    op.drop_index('ix_capacity_incoming_status', table_name='capacity_incoming')
    op.drop_index('ix_capacity_incoming_supplier_id', table_name='capacity_incoming')
    op.drop_column('capacity_incoming', 'actual_operational')
    op.drop_column('capacity_incoming', 'actual_delivery')
    op.drop_column('capacity_incoming', 'currency')
    op.drop_column('capacity_incoming', 'unit_price')
    op.drop_column('capacity_incoming', 'status')
    op.drop_column('capacity_incoming', 'supplier_id')
    op.drop_index('ix_supplier_contacts_supplier_id', table_name='supplier_contacts')
    op.drop_table('supplier_contacts')
    op.drop_index('ix_suppliers_name', table_name='suppliers')
    op.drop_table('suppliers')
