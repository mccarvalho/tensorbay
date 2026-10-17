"""Sales & Opportunity models (EPIC 03 / product plan section 9).

Models the commercial funnel: Opportunity -> Quote -> QuoteItem. A Quote is a
priced proposal derived from an Opportunity; QuoteItems are the per-SKU lines.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, TenantMixin, UUIDMixin


class SalesStage(StrEnum):
    PROSPECTING = "PROSPECTING"
    QUALIFICATION = "QUALIFICATION"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    WON = "WON"
    LOST = "LOST"


class QuoteStatus(StrEnum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class Opportunity(Base, UUIDMixin, AuditMixin, TenantMixin):
    __tablename__ = "opportunities"

    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    gpu_model: Mapped[str] = mapped_column(String(128), nullable=False)
    sku_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    expected_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    duration_months: Mapped[int] = mapped_column(Integer, nullable=False)
    commercial_model: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_mrr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    probability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales_stage: Mapped[SalesStage] = mapped_column(
        String(32), nullable=False, default=SalesStage.PROSPECTING
    )
    account_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_owner_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_owner_sub: Mapped[str | None] = mapped_column(String(64), nullable=True)

    quotes: Mapped[list["Quote"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class Quote(Base, UUIDMixin, AuditMixin, TenantMixin):
    __tablename__ = "quotes"

    opportunity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    quote_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[QuoteStatus] = mapped_column(
        String(32), nullable=False, default=QuoteStatus.DRAFT
    )
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    commitment: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sla: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    opportunity: Mapped["Opportunity"] = relationship(back_populates="quotes")
    items: Mapped[list["QuoteItem"]] = relationship(
        back_populates="quote", cascade="all, delete-orphan"
    )


class QuoteItem(Base, UUIDMixin, AuditMixin):
    __tablename__ = "quote_items"

    quote_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sku_id: Mapped[str] = mapped_column(String(36), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0")
    )

    quote: Mapped["Quote"] = relationship(back_populates="items")
