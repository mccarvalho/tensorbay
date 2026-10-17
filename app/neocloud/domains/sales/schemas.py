"""Sales & Opportunity pydantic schemas (pydantic v2)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.sales.models import QuoteStatus, SalesStage

# --------------------------------------------------------------------------- #
# Opportunity
# --------------------------------------------------------------------------- #


class OpportunityBase(BaseModel):
    customer_id: str
    gpu_model: str
    sku_id: str | None = None
    quantity: int = Field(gt=0)
    expected_start: date | None = None
    duration_months: int = Field(gt=0)
    commercial_model: str
    expected_mrr: Decimal
    probability: int = Field(default=0, ge=0, le=100)
    sales_stage: SalesStage = SalesStage.PROSPECTING
    account_owner: str | None = None
    account_owner_email: str | None = None
    account_owner_sub: str | None = None


class OpportunityCreate(OpportunityBase):
    pass


class OpportunityUpdate(BaseModel):
    customer_id: str | None = None
    gpu_model: str | None = None
    sku_id: str | None = None
    quantity: int | None = Field(default=None, gt=0)
    expected_start: date | None = None
    duration_months: int | None = Field(default=None, gt=0)
    commercial_model: str | None = None
    expected_mrr: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    sales_stage: SalesStage | None = None
    account_owner: str | None = None
    account_owner_email: str | None = None
    account_owner_sub: str | None = None


class OpportunityRead(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# QuoteItem
# --------------------------------------------------------------------------- #


class QuoteItemBase(BaseModel):
    sku_id: str
    quantity: int = Field(gt=0)
    unit_price: Decimal
    discount_pct: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class QuoteItemCreate(QuoteItemBase):
    pass


class QuoteItemRead(QuoteItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    quote_id: str


# --------------------------------------------------------------------------- #
# Quote
# --------------------------------------------------------------------------- #


class QuoteBase(BaseModel):
    opportunity_id: str
    quote_number: str
    status: QuoteStatus = QuoteStatus.DRAFT
    term_months: int = Field(gt=0)
    commitment: Decimal | None = None
    sla: str | None = None
    valid_until: date | None = None
    total_amount: Decimal = Decimal("0")


class QuoteCreate(QuoteBase):
    items: list[QuoteItemCreate] = Field(default_factory=list)


class QuoteUpdate(BaseModel):
    quote_number: str | None = None
    status: QuoteStatus | None = None
    term_months: int | None = Field(default=None, gt=0)
    commitment: Decimal | None = None
    sla: str | None = None
    valid_until: date | None = None
    total_amount: Decimal | None = None


class QuoteRead(QuoteBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[QuoteItemRead] = Field(default_factory=list)
