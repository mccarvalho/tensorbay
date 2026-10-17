"""Pydantic v2 schemas for the Capacity Management module."""

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIALLY_AVAILABLE = "PARTIALLY_AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"


class CapacityLedger(BaseModel):
    """Commercial capacity view for a GPU model (plan section 12)."""

    gpu_model: str
    physical: int
    offline: int
    maintenance: int
    operational: int
    reserved: int
    allocated: int
    available: int


class AvailabilityCheck(BaseModel):
    """Result of an overselling-prevention check (plan section 9)."""

    gpu_model: str
    requested: int
    available: int
    gap: int
    incoming: int
    status: AvailabilityStatus


# --- Incoming capacity ---
class IncomingCapacityCreate(BaseModel):
    gpu_model: str = Field(..., max_length=64)
    quantity: int = Field(..., ge=0)
    expected_delivery: date | None = None
    expected_operational: date | None = None
    purchase_order: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class IncomingCapacityUpdate(BaseModel):
    gpu_model: str | None = Field(default=None, max_length=64)
    quantity: int | None = Field(default=None, ge=0)
    expected_delivery: date | None = None
    expected_operational: date | None = None
    purchase_order: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class IncomingCapacityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gpu_model: str
    quantity: int
    expected_delivery: date | None
    expected_operational: date | None
    purchase_order: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
