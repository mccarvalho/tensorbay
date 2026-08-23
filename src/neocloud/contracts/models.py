import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class ContractStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    ACTIVE = "ACTIVE"
    EXPIRING = "EXPIRING"
    EXPIRED = "EXPIRED"
    TERMINATED = "TERMINATED"
    AMENDMENT_PENDING = "AMENDMENT_PENDING"


class BillingModel(str, enum.Enum):
    USAGE = "USAGE"
    COMMITTED = "COMMITTED"
    RESERVED = "RESERVED"
    PREPAID = "PREPAID"
    HYBRID = "HYBRID"


class CommitmentType(str, enum.Enum):
    MINIMUM_SPEND = "MINIMUM_SPEND"
    MINIMUM_GPUS = "MINIMUM_GPUS"
    MINIMUM_HOURS = "MINIMUM_HOURS"


class CommitmentPeriod(str, enum.Enum):
    MONTHLY = "MONTHLY"
    QUARTERLY = "QUARTERLY"
    ANNUAL = "ANNUAL"


class PricingModel(str, enum.Enum):
    FLAT = "FLAT"
    TIERED = "TIERED"
    VOLUME = "VOLUME"
    STEP = "STEP"


class SLATier(str, enum.Enum):
    STANDARD = "STANDARD"
    PREMIUM = "PREMIUM"
    ENTERPRISE = "ENTERPRISE"


class Contract(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contracts"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    billing_account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("billing_accounts.id"), nullable=False)
    quote_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contract_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    status: Mapped[ContractStatus] = mapped_column(Enum(ContractStatus), default=ContractStatus.DRAFT)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    term_months: Mapped[int] = mapped_column(Integer, nullable=False)
    auto_renewal: Mapped[bool] = mapped_column(Boolean, default=False)
    renewal_term_months: Mapped[int | None] = mapped_column(Integer)
    notice_period_days: Mapped[int] = mapped_column(Integer, default=30)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    total_contract_value: Mapped[float | None] = mapped_column(Float)
    sla_tier: Mapped[str | None] = mapped_column(String(50))
    commercial_notes: Mapped[str | None] = mapped_column(Text)
    document_reference: Mapped[str | None] = mapped_column(String(500))
    signed_by_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    items: Mapped[list["ContractItem"]] = relationship(back_populates="contract", lazy="selectin")
    commitments: Mapped[list["Commitment"]] = relationship(back_populates="contract", lazy="selectin")
    pricing_agreements: Mapped[list["PricingAgreement"]] = relationship(back_populates="contract", lazy="selectin")
    slas: Mapped[list["SLA"]] = relationship(back_populates="contract", lazy="selectin")


class ContractItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contract_items"

    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    line_value_monthly: Mapped[float] = mapped_column(Float, nullable=False)
    billing_model: Mapped[BillingModel] = mapped_column(Enum(BillingModel), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))

    contract: Mapped["Contract"] = relationship(back_populates="items")


class Commitment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "commitments"

    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    type: Mapped[CommitmentType] = mapped_column(Enum(CommitmentType), nullable=False)
    minimum_value: Mapped[float] = mapped_column(Float, nullable=False)
    period: Mapped[CommitmentPeriod] = mapped_column(Enum(CommitmentPeriod), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    overage_rate: Mapped[float | None] = mapped_column(Float)
    rollover_unused: Mapped[bool] = mapped_column(Boolean, default=False)

    contract: Mapped["Contract"] = relationship(back_populates="commitments")


class PricingAgreement(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "pricing_agreements"

    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=False)
    agreed_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    pricing_model: Mapped[PricingModel] = mapped_column(Enum(PricingModel), default=PricingModel.FLAT)
    tiers: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date] = mapped_column(Date, nullable=False)

    contract: Mapped["Contract"] = relationship(back_populates="pricing_agreements")


class SLA(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "slas"

    contract_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[SLATier] = mapped_column(Enum(SLATier), default=SLATier.STANDARD)
    uptime_pct: Mapped[float] = mapped_column(Float, default=99.9)
    response_time_minutes: Mapped[int] = mapped_column(Integer, default=60)
    resolution_time_hours: Mapped[int] = mapped_column(Integer, default=24)
    credit_pct_per_breach: Mapped[float] = mapped_column(Float, default=5.0)
    max_credit_pct: Mapped[float] = mapped_column(Float, default=30.0)

    contract: Mapped["Contract"] = relationship(back_populates="slas")
