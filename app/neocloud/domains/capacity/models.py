"""Capacity Management models (product plan section 12 / EPIC 06).

The capacity ledger is computed on demand from the GPU asset inventory. Future
supply is persisted as IncomingCapacity rows (Future Capacity): hardware ordered
but not yet installed. A SupplyOrder groups the delivery lots of one supplier
contract (e.g. 64 HGX B300 servers = 512 GPUs from Positivo) so the whole order
is registered once, by totals, without creating SKU-level assets.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class ProcurementStatus(StrEnum):
    """Lifecycle of an incoming-capacity (hardware procurement) record."""

    NEGOTIATING = "NEGOTIATING"
    ORDERED = "ORDERED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    OPERATIONAL = "OPERATIONAL"


# Statuses that represent committed supply (counted in the capacity ledger as
# incoming). NEGOTIATING is pipeline-only and must NOT be counted as committed.
COMMITTED_PROCUREMENT_STATUSES = frozenset(
    {
        ProcurementStatus.ORDERED,
        ProcurementStatus.IN_TRANSIT,
        ProcurementStatus.DELIVERED,
        ProcurementStatus.OPERATIONAL,
    }
)


class IncomingCapacity(Base, UUIDMixin, AuditMixin):
    __tablename__ = "capacity_incoming"

    gpu_model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    status: Mapped[ProcurementStatus] = mapped_column(
        String(16), nullable=False, default=ProcurementStatus.NEGOTIATING, index=True
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # Estimated dates (while NEGOTIATING / ORDERED / IN_TRANSIT)
    expected_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_operational: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Official / actual dates (once DELIVERED / OPERATIONAL)
    actual_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    actual_operational: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_order: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Delivery lot of a SupplyOrder (null = standalone incoming record).
    order_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("capacity_supply_orders.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    lot_label: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SupplyOrder(Base, UUIDMixin, AuditMixin):
    """One supplier contract for GPU servers, recorded by totals.

    Its delivery lots are IncomingCapacity rows (``order_id``). The order holds
    what is contracted; the lots hold when it arrives. Individual servers and
    GPUs are added to Inventory later, when serial numbers are known.
    """

    __tablename__ = "capacity_supply_orders"

    reference: Mapped[str] = mapped_column(String(128), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=True, index=True
    )
    supplier_quote: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[ProcurementStatus] = mapped_column(
        String(16), nullable=False, default=ProcurementStatus.ORDERED, index=True
    )
    signed_on: Mapped[date | None] = mapped_column(Date, nullable=True)

    gpu_model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    server_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    gpus_per_server: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    servers: Mapped[int] = mapped_column(Integer, nullable=False)
    gpus_total: Mapped[int] = mapped_column(Integer, nullable=False)

    unit_price_per_server: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    total_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)

    assembly_site: Mapped[str | None] = mapped_column(String(255), nullable=True)
    destination_site: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_regime: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_window: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
