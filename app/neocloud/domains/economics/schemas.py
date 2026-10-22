"""Pydantic v2 schemas for the Economics & Commissions module (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.economics.models import ArrType, DealStatus, RepStatus, RepType


# --------------------------------------------------------------------------- #
# Sales representatives / finders
# --------------------------------------------------------------------------- #
class SalesRepBase(BaseModel):
    name: str = Field(..., max_length=255)
    email: str | None = Field(default=None, max_length=320)
    type: RepType
    status: RepStatus = RepStatus.ACTIVE
    base_salary: Decimal | None = Field(default=None, ge=0)
    cognito_sub: str | None = Field(default=None, max_length=64)
    payment_details: str | None = None
    notes: str | None = None


class SalesRepCreate(SalesRepBase):
    pass


class SalesRepUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    type: RepType | None = None
    status: RepStatus | None = None
    base_salary: Decimal | None = Field(default=None, ge=0)
    cognito_sub: str | None = Field(default=None, max_length=64)
    payment_details: str | None = None
    notes: str | None = None


class SalesRepRead(SalesRepBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Commission plans
# --------------------------------------------------------------------------- #
class CommissionPlanBase(BaseModel):
    name: str = Field(..., max_length=128)
    plan_year: int = Field(..., ge=2020, le=2100)
    ae_rate: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    am_rate: Decimal = Field(default=Decimal("0.10"), ge=0, le=1)
    finder_rate: Decimal = Field(default=Decimal("0.03"), ge=0, le=1)
    ae_quota_arr: Decimal = Field(default=Decimal("6000000"), ge=0)
    am_quota_arr: Decimal = Field(default=Decimal("3000000"), ge=0)
    default_margin_pct: Decimal = Field(default=Decimal("0.30"), ge=0, le=1)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True
    notes: str | None = None


class CommissionPlanCreate(CommissionPlanBase):
    pass


class CommissionPlanUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    plan_year: int | None = Field(default=None, ge=2020, le=2100)
    ae_rate: Decimal | None = Field(default=None, ge=0, le=1)
    am_rate: Decimal | None = Field(default=None, ge=0, le=1)
    finder_rate: Decimal | None = Field(default=None, ge=0, le=1)
    ae_quota_arr: Decimal | None = Field(default=None, ge=0)
    am_quota_arr: Decimal | None = Field(default=None, ge=0)
    default_margin_pct: Decimal | None = Field(default=None, ge=0, le=1)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None
    notes: str | None = None


class CommissionPlanRead(CommissionPlanBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Commission deals (Phase 2)
# --------------------------------------------------------------------------- #
class CommissionDealBase(BaseModel):
    name: str = Field(..., max_length=255)
    customer_id: str = Field(..., max_length=36)
    opportunity_id: str | None = Field(default=None, max_length=36)
    plan_id: str | None = Field(default=None, max_length=36)
    arr_type: ArrType = ArrType.NEW_LOGO
    arr: Decimal = Field(..., ge=0)
    margin_pct: Decimal | None = Field(default=None, ge=0, le=1)
    ae_id: str | None = Field(default=None, max_length=36)
    am_id: str | None = Field(default=None, max_length=36)
    is_referred: bool = False
    finder_id: str | None = Field(default=None, max_length=36)
    booked_date: date
    notes: str | None = None


class CommissionDealCreate(CommissionDealBase):
    pass


class CommissionDealFromOpportunity(BaseModel):
    """Create a deal from a won opportunity; ARR defaults to MRR x 12."""

    opportunity_id: str = Field(..., max_length=36)
    arr_type: ArrType = ArrType.NEW_LOGO
    arr: Decimal | None = Field(default=None, ge=0)  # override; else MRR*12
    margin_pct: Decimal | None = Field(default=None, ge=0, le=1)
    ae_id: str | None = None
    am_id: str | None = None
    is_referred: bool = False
    finder_id: str | None = None
    booked_date: date | None = None
    notes: str | None = None


class CommissionDealUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    arr_type: ArrType | None = None
    arr: Decimal | None = Field(default=None, ge=0)
    margin_pct: Decimal | None = Field(default=None, ge=0, le=1)
    ae_id: str | None = None
    am_id: str | None = None
    is_referred: bool | None = None
    finder_id: str | None = None
    booked_date: date | None = None
    notes: str | None = None


class CommissionDealApprove(BaseModel):
    """Super Admin approval; may adjust rate-relevant fields before approving."""

    margin_pct: Decimal | None = Field(default=None, ge=0, le=1)
    is_referred: bool | None = None
    finder_id: str | None = None
    acknowledge_margin_warning: bool = False


class CommissionDealReject(BaseModel):
    reason: str = Field(..., max_length=1024)


class CommissionDealRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    customer_id: str
    opportunity_id: str | None
    plan_id: str | None
    arr_type: ArrType
    arr: Decimal
    margin_pct: Decimal
    gross_profit: Decimal
    ae_id: str | None
    am_id: str | None
    is_referred: bool
    finder_id: str | None
    booked_date: date
    plan_year: int
    status: DealStatus
    margin_warning: bool
    approved_by: str | None
    approved_at: datetime | None
    rejection_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Commission runs & statements (Phase 3)
# --------------------------------------------------------------------------- #
from neocloud.domains.economics.models import (  # noqa: E402
    CommissionComponent,
    PaymentStatus,
    RunStatus,
)


class CommissionRunCreate(BaseModel):
    plan_year: int = Field(..., ge=2020, le=2100)
    quarter: int = Field(..., ge=1, le=4)
    notes: str | None = None


class CommissionStatementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    run_id: str
    rep_id: str
    component: CommissionComponent
    plan_year: int
    quarter: int
    ytd_arr: Decimal
    quota_arr: Decimal
    gate_cleared: bool
    rate: Decimal
    ytd_gross_profit: Decimal
    ytd_earned: Decimal
    prior_paid: Decimal
    amount: Decimal
    payment_status: PaymentStatus
    paid_at: datetime | None
    payment_reference: str | None
    created_at: datetime
    updated_at: datetime


class CommissionRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    plan_year: int
    quarter: int
    plan_id: str | None
    status: RunStatus
    total_commission: Decimal
    notes: str | None
    created_at: datetime
    updated_at: datetime


class CommissionRunDetail(CommissionRunRead):
    statements: list[CommissionStatementRead] = Field(default_factory=list)


class StatementMarkPaid(BaseModel):
    payment_reference: str | None = Field(default=None, max_length=255)


# --------------------------------------------------------------------------- #
# Cost items (Phase 4)
# --------------------------------------------------------------------------- #
from neocloud.domains.economics.models import CostCategory, CostPeriod  # noqa: E402


class CostItemBase(BaseModel):
    name: str = Field(..., max_length=255)
    category: CostCategory
    amount: Decimal = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=3)
    period: CostPeriod = CostPeriod.ONE_TIME
    incurred_on: date | None = None
    customer_id: str | None = Field(default=None, max_length=36)
    deal_id: str | None = Field(default=None, max_length=36)
    supplier_id: str | None = Field(default=None, max_length=36)
    notes: str | None = None


class CostItemCreate(CostItemBase):
    pass


class CostItemUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    category: CostCategory | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    period: CostPeriod | None = None
    incurred_on: date | None = None
    customer_id: str | None = Field(default=None, max_length=36)
    deal_id: str | None = Field(default=None, max_length=36)
    supplier_id: str | None = Field(default=None, max_length=36)
    notes: str | None = None


class CostItemRead(CostItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime


class DealEconomics(BaseModel):
    """Real-margin view for a deal: ARR, nominal margin, and actual cost."""

    deal_id: str
    arr: Decimal
    nominal_margin_pct: Decimal
    nominal_gross_profit: Decimal
    allocated_cost: Decimal
    real_gross_profit: Decimal
    real_margin_pct: Decimal | None
