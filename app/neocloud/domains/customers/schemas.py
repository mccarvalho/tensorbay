"""Pydantic v2 schemas for Customer Management."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr

from neocloud.domains.customers.models import (
    ActivityType,
    ContactType,
    CreditStatus,
    CustomerStatus,
)

# --------------------------------------------------------------------------- #
# Customer
# --------------------------------------------------------------------------- #


class CustomerBase(BaseModel):
    legal_name: str
    trading_name: str | None = None
    tax_id: str | None = None
    country: str | None = None
    currency: str | None = None
    status: CustomerStatus = CustomerStatus.PROSPECT
    credit_status: CreditStatus = CreditStatus.GOOD
    account_owner: str | None = None
    industry: str | None = None
    parent_company_id: str | None = None


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    legal_name: str | None = None
    trading_name: str | None = None
    tax_id: str | None = None
    country: str | None = None
    currency: str | None = None
    status: CustomerStatus | None = None
    credit_status: CreditStatus | None = None
    account_owner: str | None = None
    industry: str | None = None
    parent_company_id: str | None = None


class CustomerResponse(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None


# --------------------------------------------------------------------------- #
# Contact
# --------------------------------------------------------------------------- #


class ContactBase(BaseModel):
    type: ContactType
    name: str
    email: EmailStr | None = None
    phone: str | None = None


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    type: ContactType | None = None
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None


class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------------- #
# Activity (CRM touchpoint)
# --------------------------------------------------------------------------- #


class ActivityBase(BaseModel):
    type: ActivityType
    subject: str
    notes: str | None = None
    outcome: str | None = None
    occurred_at: datetime | None = None
    next_follow_up_date: date | None = None
    contact_id: str | None = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    type: ActivityType | None = None
    subject: str | None = None
    notes: str | None = None
    outcome: str | None = None
    occurred_at: datetime | None = None
    next_follow_up_date: date | None = None
    contact_id: str | None = None


class ActivityResponse(ActivityBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    occurred_at: datetime
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None


# --------------------------------------------------------------------------- #
# BillingAccount
# --------------------------------------------------------------------------- #


class BillingAccountBase(BaseModel):
    billing_address: str | None = None
    currency: str | None = None
    payment_terms: str | None = None
    credit_limit: Decimal | None = None
    tax_config: dict[str, Any] | None = None
    invoice_preferences: dict[str, Any] | None = None


class BillingAccountCreate(BillingAccountBase):
    pass


class BillingAccountUpdate(BillingAccountBase):
    pass


class BillingAccountResponse(BillingAccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    customer_id: str
    created_at: datetime
    updated_at: datetime
