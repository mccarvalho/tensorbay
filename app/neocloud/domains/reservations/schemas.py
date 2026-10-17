"""Reservation & Allocation pydantic schemas (pydantic v2)."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.reservations.models import (
    AllocationStatus,
    ReservationStatus,
)

# --------------------------------------------------------------------------- #
# AllocationGpu
# --------------------------------------------------------------------------- #


class AllocationGpuRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    allocation_id: str
    gpu_asset_id: str


# --------------------------------------------------------------------------- #
# Allocation
# --------------------------------------------------------------------------- #


class AllocationBase(BaseModel):
    status: AllocationStatus = AllocationStatus.RESERVED
    cluster_id: str | None = None
    notes: str | None = None


class AllocationCreate(AllocationBase):
    gpu_asset_ids: list[str] = Field(default_factory=list)


class AllocationUpdate(BaseModel):
    status: AllocationStatus | None = None
    cluster_id: str | None = None
    notes: str | None = None


class AllocationRead(AllocationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reservation_id: str
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    gpus: list[AllocationGpuRead] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Reservation
# --------------------------------------------------------------------------- #


class ReservationBase(BaseModel):
    contract_id: str
    customer_id: str
    gpu_model: str
    quantity: int = Field(gt=0)
    start_date: date
    end_date: date | None = None
    status: ReservationStatus = ReservationStatus.PENDING


class ReservationCreate(ReservationBase):
    pass


class ReservationUpdate(BaseModel):
    gpu_model: str | None = None
    quantity: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    status: ReservationStatus | None = None


class ReservationRead(ReservationBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    allocations: list[AllocationRead] = Field(default_factory=list)
