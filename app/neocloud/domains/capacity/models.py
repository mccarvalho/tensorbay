"""Capacity Management models (product plan section 12 / EPIC 06).

The capacity ledger is computed on demand from the GPU asset inventory, so
the only persisted table here is IncomingCapacity (Future Capacity): hardware
that has been ordered but is not yet physically installed/operational.
"""

from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class IncomingCapacity(Base, UUIDMixin, AuditMixin):
    __tablename__ = "capacity_incoming"

    gpu_model: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_delivery: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_operational: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_order: Mapped[str | None] = mapped_column(String(128), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
