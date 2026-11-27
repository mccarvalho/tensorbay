"""Sales & Opportunity pydantic schemas (pydantic v2)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from neocloud.domains.sales.models import GPUS_PER_SERVER, QuoteStatus, SalesStage

# --------------------------------------------------------------------------- #
# Opportunity
# --------------------------------------------------------------------------- #


def _whole_servers(v: int | None) -> int | None:
    if v is not None and v % GPUS_PER_SERVER:
        raise ValueError(f"GPUs are sold in whole servers: use a multiple of {GPUS_PER_SERVER}")
    return v


class OpportunityBase(BaseModel):
    customer_id: str
    short_name: str | None = Field(default=None, max_length=60)
    gpu_model: str
    sku_id: str | None = None
    quantity: int = Field(gt=0)
    expected_start: date | None = None
    duration_months: int = Field(gt=0)
    commercial_model: str
    expected_mrr: Decimal
    probability: int = Field(default=0, ge=0, le=100)
    sales_stage: SalesStage = SalesStage.NEW_LEAD
    region: str | None = Field(default=None, max_length=64)
    assigned_to: str | None = Field(default=None, max_length=255)
    next_action: str | None = Field(default=None, max_length=255)
    escrow_required: bool = True
    upfront_pct: Decimal | None = Field(default=None, gt=0, lt=100)
    node_spec: str | None = Field(default=None, max_length=500)
    payment_structure: Literal["A", "B", "C", "D"] | None = None
    first_delivery_date: date | None = None
    latest_delivery_date: date | None = None
    account_owner: str | None = None
    account_owner_email: str | None = None
    account_owner_sub: str | None = None


class OpportunityCreate(OpportunityBase):
    # Only new and edited deals: older deals with other sizes must still be listed.
    _servers = field_validator("quantity")(_whole_servers)


class OpportunityUpdate(BaseModel):
    customer_id: str | None = None
    short_name: str | None = Field(default=None, max_length=60)
    gpu_model: str | None = None
    sku_id: str | None = None
    quantity: int | None = Field(default=None, gt=0)
    expected_start: date | None = None
    duration_months: int | None = Field(default=None, gt=0)
    commercial_model: str | None = None
    expected_mrr: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    sales_stage: SalesStage | None = None
    region: str | None = Field(default=None, max_length=64)
    assigned_to: str | None = Field(default=None, max_length=255)
    next_action: str | None = Field(default=None, max_length=255)
    escrow_required: bool | None = None
    upfront_pct: Decimal | None = Field(default=None, gt=0, lt=100)
    node_spec: str | None = Field(default=None, max_length=500)
    payment_structure: Literal["A", "B", "C", "D"] | None = None
    first_delivery_date: date | None = None
    latest_delivery_date: date | None = None
    account_owner: str | None = None
    account_owner_email: str | None = None
    account_owner_sub: str | None = None

    _servers = field_validator("quantity")(_whole_servers)


class InventoryLane(BaseModel):
    gpu_model: str
    physical: int
    allocated: int
    reserved: int
    available: int
    incoming: int
    open_demand: int


class OpportunityRead(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    stage_before_hold: str | None = None
    min_order_status: str | None = None
    min_order_approved_by: str | None = None
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
