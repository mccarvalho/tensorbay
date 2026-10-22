"""Pydantic v2 schemas for the Economics & Commissions module (Phase 1)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.economics.models import RepStatus, RepType


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
