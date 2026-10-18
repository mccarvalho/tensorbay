"""Supplier / Distributor models.

A Supplier is the counterparty we procure GPU hardware/capacity from
(OEMs like NVIDIA, distributors/resellers, cloud providers like Oracle, or
brokers). Incoming capacity (future hardware) links back to a Supplier so the
team can track multiple negotiations across multiple suppliers.
"""

from enum import StrEnum

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class SupplierTier(StrEnum):
    OEM = "OEM"
    DISTRIBUTOR = "DISTRIBUTOR"
    CLOUD = "CLOUD"
    BROKER = "BROKER"


class SupplierStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class Supplier(Base, UUIDMixin, AuditMixin):
    __tablename__ = "suppliers"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tier: Mapped[SupplierTier] = mapped_column(
        String(16), nullable=False, default=SupplierTier.DISTRIBUTOR
    )
    status: Mapped[SupplierStatus] = mapped_column(
        String(16), nullable=False, default=SupplierStatus.ACTIVE
    )
    country: Mapped[str | None] = mapped_column(String(2))
    website: Mapped[str | None] = mapped_column(String(255))
    account_manager: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contacts: Mapped[list["SupplierContact"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan"
    )


class SupplierContact(Base, UUIDMixin, AuditMixin):
    __tablename__ = "supplier_contacts"

    supplier_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("suppliers.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))

    supplier: Mapped["Supplier"] = relationship(back_populates="contacts")
