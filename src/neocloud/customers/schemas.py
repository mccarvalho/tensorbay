import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from neocloud.customers.models import (
    BillingAccountStatus,
    ContactRole,
    CreditStatus,
    CustomerStatus,
    InvoicePreference,
    TaxConfig,
)


# --- Customer Schemas ---


class CustomerCreate(BaseModel):
    legal_name: str
    trading_name: str | None = None
    tax_id: str | None = None
    country: str
    currency: str = "USD"
    industry: str | None = None
    parent_customer_id: uuid.UUID | None = None
    account_owner_id: uuid.UUID | None = None


class CustomerUpdate(BaseModel):
    legal_name: str | None = None
    trading_name: str | None = None
    tax_id: str | None = None
    country: str | None = None
    currency: str | None = None
    status: CustomerStatus | None = None
    credit_status: CreditStatus | None = None
    industry: str | None = None
    parent_customer_id: uuid.UUID | None = None
    account_owner_id: uuid.UUID | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    trading_name: str | None
    tax_id: str | None
    country: str
    currency: str
    status: CustomerStatus
    credit_status: CreditStatus
    parent_customer_id: uuid.UUID | None
    account_owner_id: uuid.UUID | None
    industry: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# --- Contact Schemas ---


class ContactCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    role: ContactRole
    is_primary: bool = False


class ContactResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    phone: str | None
    role: ContactRole
    is_primary: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Billing Account Schemas ---


class BillingAccountCreate(BaseModel):
    name: str
    billing_address_line1: str
    billing_address_line2: str | None = None
    billing_city: str
    billing_state: str | None = None
    billing_country: str
    billing_postal_code: str
    currency: str = "USD"
    payment_terms_days: int = 30
    credit_limit: float | None = None
    tax_config: TaxConfig = TaxConfig.TAXABLE
    invoice_preference: InvoicePreference = InvoicePreference.EMAIL


class BillingAccountResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    name: str
    billing_address_line1: str
    billing_city: str
    billing_country: str
    billing_postal_code: str
    currency: str
    payment_terms_days: int
    credit_limit: float | None
    tax_config: TaxConfig
    invoice_preference: InvoicePreference
    status: BillingAccountStatus
    created_at: datetime

    model_config = {"from_attributes": True}
