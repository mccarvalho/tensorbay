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
