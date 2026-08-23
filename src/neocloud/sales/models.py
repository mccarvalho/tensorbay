import enum
import uuid
from datetime import date

from sqlalchemy import Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class OpportunityStage(str, enum.Enum):
    QUALIFICATION = "QUALIFICATION"
    DISCOVERY = "DISCOVERY"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"


class CommercialModel(str, enum.Enum):
    HOURLY = "HOURLY"
    MONTHLY = "MONTHLY"
    RESERVED = "RESERVED"
    COMMITTED = "COMMITTED"
    PREPAID = "PREPAID"
    SPOT = "SPOT"


class QuoteStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class CapacityCheckResult(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class Opportunity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "opportunities"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    account_owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sku_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=True)
    gpu_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(50), nullable=False)
    expected_start: Mapped[date | None] = mapped_column(Date)
    duration_months: Mapped[int | None] = mapped_column(Integer)
    commercial_model: Mapped[CommercialModel] = mapped_column(Enum(CommercialModel), nullable=False)
    expected_mrr: Mapped[float | None] = mapped_column(Float)
    probability_pct: Mapped[float] = mapped_column(Float, default=0)
    stage: Mapped[OpportunityStage] = mapped_column(Enum(OpportunityStage), default=OpportunityStage.QUALIFICATION)
    region: Mapped[str | None] = mapped_column(String(50))
    notes: Mapped[str | None] = mapped_column(Text)
    expected_close_date: Mapped[date | None] = mapped_column(Date)

    quotes: Mapped[list["Quote"]] = relationship(back_populates="opportunity", lazy="selectin")
    capacity_checks: Mapped[list["CapacityCheck"]] = relationship(back_populates="opportunity", lazy="selectin")


class CapacityCheck(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "capacity_checks"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False)
    requested_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    gpu_model: Mapped[str] = mapped_column(String(50), nullable=False)
    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    region: Mapped[str | None] = mapped_column(String(50))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    available_now: Mapped[int] = mapped_column(Integer, default=0)
    reserved_current: Mapped[int] = mapped_column(Integer, default=0)
    incoming_capacity: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[CapacityCheckResult] = mapped_column(Enum(CapacityCheckResult), nullable=False)
    capacity_gap: Mapped[int] = mapped_column(Integer, default=0)
    full_capacity_date: Mapped[date | None] = mapped_column(Date)
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="capacity_checks")


class Quote(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "quotes"

    opportunity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=False)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    prepared_by_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    quote_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus), default=QuoteStatus.DRAFT)
    valid_until: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Float, default=0)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    sla_tier: Mapped[str | None] = mapped_column(String(50))
    commercial_terms: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="quotes")
    items: Mapped[list["QuoteItem"]] = relationship(back_populates="quote", lazy="selectin")


class QuoteItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "quote_items"

    quote_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("quotes.id"), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    discount_pct: Mapped[float] = mapped_column(Float, default=0)
    line_total: Mapped[float] = mapped_column(Float, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    quote: Mapped["Quote"] = relationship(back_populates="items")
