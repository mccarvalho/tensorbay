"""Capacity Management models (product plan section 12 / EPIC 06).

The capacity ledger is computed on demand from the GPU asset inventory, so
the only persisted table here is IncomingCapacity (Future Capacity): hardware
that has been ordered but is not yet physically installed/operational.
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
