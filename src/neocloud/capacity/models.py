import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class LedgerEntryType(str, enum.Enum):
    PHYSICAL_ADD = "PHYSICAL_ADD"
    PHYSICAL_REMOVE = "PHYSICAL_REMOVE"
    OFFLINE = "OFFLINE"
    ONLINE = "ONLINE"
    MAINTENANCE_START = "MAINTENANCE_START"
    MAINTENANCE_END = "MAINTENANCE_END"
    RESERVE = "RESERVE"
    RELEASE_RESERVE = "RELEASE_RESERVE"
    ALLOCATE = "ALLOCATE"
    RELEASE_ALLOCATE = "RELEASE_ALLOCATE"
    INCOMING_PLANNED = "INCOMING_PLANNED"
    INCOMING_CONFIRMED = "INCOMING_CONFIRMED"
    INCOMING_DELIVERED = "INCOMING_DELIVERED"


class IncomingCapacityStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    ORDERED = "ORDERED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    INSTALLED = "INSTALLED"
    OPERATIONAL = "OPERATIONAL"


class CapacityLedgerEntry(Base, UUIDMixin):
    """Append-only ledger tracking all capacity changes."""
    __tablename__ = "capacity_ledger"

    gpu_model: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    datacenter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    entry_type: Mapped[LedgerEntryType] = mapped_column(Enum(LedgerEntryType), nullable=False)
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False)
    running_total_physical: Mapped[int] = mapped_column(Integer, nullable=False)
    running_total_operational: Mapped[int] = mapped_column(Integer, nullable=False)
    running_total_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    running_total_allocated: Mapped[int] = mapped_column(Integer, nullable=False)
    running_total_available: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reference_type: Mapped[str | None] = mapped_column(String(50))
    reason: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)


class IncomingCapacity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "incoming_capacity"

    gpu_model: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    supplier: Mapped[str] = mapped_column(String(255), nullable=False)
    purchase_order_number: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    datacenter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[IncomingCapacityStatus] = mapped_column(Enum(IncomingCapacityStatus), default=IncomingCapacityStatus.PLANNED)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    expected_operational_date: Mapped[date | None] = mapped_column(Date)
    actual_delivery_date: Mapped[date | None] = mapped_column(Date)
    actual_operational_date: Mapped[date | None] = mapped_column(Date)
    total_cost: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    notes: Mapped[str | None] = mapped_column(Text)
