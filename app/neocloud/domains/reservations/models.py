"""Reservation & Allocation models (EPIC 07 / product plan section 13).

Two deliberately separate concepts (per the plan, these states must remain
separate):

* Reservation  -- the COMMERCIAL commitment: "customer X reserves N GPUs of a
  given model for a period". It does NOT bind to specific hardware.
* Allocation   -- the PHYSICAL/LOGICAL binding fulfilling a reservation. Links
  to concrete GpuAsset rows via the AllocationGpu association.
"""

from datetime import date
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, TenantMixin, UUIDMixin


class ReservationStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"
    CANCELLED = "CANCELLED"


class AllocationStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    PROVISIONING = "PROVISIONING"
    ALLOCATED = "ALLOCATED"
    IN_USE = "IN_USE"
    MAINTENANCE = "MAINTENANCE"
    FAILED = "FAILED"
    RELEASED = "RELEASED"
    DECOMMISSIONED = "DECOMMISSIONED"


class Reservation(Base, UUIDMixin, AuditMixin, TenantMixin):
    """Commercial reservation -- no specific hardware is bound here."""

    __tablename__ = "reservations"

    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gpu_model: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[ReservationStatus] = mapped_column(
        String(16), nullable=False, default=ReservationStatus.PENDING
    )

    allocations: Mapped[list["Allocation"]] = relationship(
        back_populates="reservation", cascade="all, delete-orphan"
    )


class Allocation(Base, UUIDMixin, AuditMixin, TenantMixin):
    """Physical/logical binding fulfilling (part of) a reservation."""

    __tablename__ = "allocations"

    reservation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AllocationStatus] = mapped_column(
        String(16), nullable=False, default=AllocationStatus.RESERVED
    )
    cluster_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    reservation: Mapped["Reservation"] = relationship(back_populates="allocations")
    gpus: Mapped[list["AllocationGpu"]] = relationship(
        back_populates="allocation", cascade="all, delete-orphan"
    )


class AllocationGpu(Base, UUIDMixin, AuditMixin):
    """Association linking an Allocation to a specific GpuAsset (inventory)."""

    __tablename__ = "allocation_gpus"
    __table_args__ = (
        UniqueConstraint("allocation_id", "gpu_asset_id", name="uq_allocation_gpu"),
    )

    allocation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("allocations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # References inventory.GpuAsset (table "inventory_gpu_assets"); the
    # inventory module owns that table. Use a string-based FK to avoid
    # cross-module import coupling while preserving the DB-level relationship.
    gpu_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("inventory_gpu_assets.id"), nullable=False, index=True
    )

    allocation: Mapped["Allocation"] = relationship(back_populates="gpus")
