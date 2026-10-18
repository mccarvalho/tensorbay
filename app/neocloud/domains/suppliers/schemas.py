"""Pydantic v2 schemas for the Suppliers module."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.suppliers.models import SupplierStatus, SupplierTier


# --- Supplier contacts ---
class SupplierContactBase(BaseModel):
    name: str = Field(..., max_length=255)
    role: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)


class SupplierContactCreate(SupplierContactBase):
    pass


class SupplierContactUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=128)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=64)


class SupplierContactRead(SupplierContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supplier_id: str
    created_at: datetime
    updated_at: datetime


# --- Suppliers ---
class SupplierBase(BaseModel):
    name: str = Field(..., max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tier: SupplierTier = SupplierTier.DISTRIBUTOR
    status: SupplierStatus = SupplierStatus.ACTIVE
    country: str | None = Field(default=None, max_length=2)
    website: str | None = Field(default=None, max_length=255)
    account_manager: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierCreate(SupplierBase):
    pass


class SupplierUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    tier: SupplierTier | None = None
    status: SupplierStatus | None = None
    country: str | None = Field(default=None, max_length=2)
    website: str | None = Field(default=None, max_length=255)
    account_manager: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierRead(SupplierBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
