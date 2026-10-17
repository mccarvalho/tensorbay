"""Contract Management models (EPIC 04 / product plan section 10).

A Contract is the legal/commercial agreement with a customer. It carries line
items (ContractItem), minimum commitments (Commitment) and negotiated prices
(PriceAgreement).
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, TenantMixin, UUIDMixin


class ContractStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    AMENDED = "AMENDED"
    RENEWED = "RENEWED"
    TERMINATED = "TERMINATED"
    EXPIRED = "EXPIRED"


class CommitmentType(StrEnum):
    MINIMUM_SPEND = "MINIMUM_SPEND"
    RESERVED_QUANTITY = "RESERVED_QUANTITY"


class CommitmentPeriod(StrEnum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class Contract(Base, UUIDMixin, AuditMixin, TenantMixin):
    __tablename__ = "contracts"

    contract_number: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[ContractStatus] = mapped_column(
        String(32), nullable=False, default=ContractStatus.DRAFT
    )
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    auto_renew: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    commercial_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_reference: Mapped[str | None] = mapped_column(String(512), nullable=True)

    items: Mapped[list["ContractItem"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    commitments: Mapped[list["Commitment"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    price_agreements: Mapped[list["PriceAgreement"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class ContractItem(Base, UUIDMixin, AuditMixin):
    __tablename__ = "contract_items"

    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="items")


class Commitment(Base, UUIDMixin, AuditMixin):
    __tablename__ = "contract_commitments"

    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[CommitmentType] = mapped_column(String(32), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    period: Mapped[CommitmentPeriod] = mapped_column(String(16), nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="commitments")


class PriceAgreement(Base, UUIDMixin, AuditMixin):
    __tablename__ = "contract_price_agreements"

    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    agreed_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="price_agreements")
