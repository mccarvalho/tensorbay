"""Pydantic v2 schemas for the GPU Asset Inventory module."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.inventory.models import (
    CommercialStatus,
    OperationalStatus,
)


# --- Region ---
class RegionCreate(BaseModel):
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)


class RegionUpdate(BaseModel):
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)


class RegionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    created_at: datetime
    updated_at: datetime


# --- Datacenter ---
class DatacenterCreate(BaseModel):
    region_id: str
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)


class DatacenterUpdate(BaseModel):
    region_id: str | None = None
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)


class DatacenterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    region_id: str
    code: str
    name: str
    created_at: datetime
    updated_at: datetime


# --- Cluster ---
class ClusterCreate(BaseModel):
    datacenter_id: str
    code: str = Field(..., max_length=32)
    name: str = Field(..., max_length=255)
    gpu_model: str = Field(..., max_length=64)


class ClusterUpdate(BaseModel):
    datacenter_id: str | None = None
    code: str | None = Field(default=None, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    gpu_model: str | None = Field(default=None, max_length=64)


class ClusterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    datacenter_id: str
    code: str
    name: str
    gpu_model: str
    created_at: datetime
    updated_at: datetime


# --- Rack ---
class RackCreate(BaseModel):
    cluster_id: str
    code: str = Field(..., max_length=32)


class RackUpdate(BaseModel):
    cluster_id: str | None = None
    code: str | None = Field(default=None, max_length=32)


class RackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cluster_id: str
    code: str
    created_at: datetime
    updated_at: datetime


# --- Server ---
class ServerCreate(BaseModel):
    rack_id: str
    code: str = Field(..., max_length=32)


class ServerUpdate(BaseModel):
    rack_id: str | None = None
    code: str | None = Field(default=None, max_length=32)


class ServerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rack_id: str
    code: str
    created_at: datetime
    updated_at: datetime


# --- GpuAsset ---
class GpuAssetCreate(BaseModel):
    server_id: str
    gpu_id: str = Field(..., max_length=64)
    manufacturer: str | None = Field(default=None, max_length=128)
    model: str = Field(..., max_length=64)
    memory_gb: int | None = None
    serial_number: str | None = Field(default=None, max_length=128)
    acquisition_cost: Decimal | None = None
    acquisition_date: date | None = None
    supplier: str | None = Field(default=None, max_length=255)
    warranty: str | None = Field(default=None, max_length=128)
    operational_status: OperationalStatus = OperationalStatus.ONLINE
    commercial_status: CommercialStatus = CommercialStatus.AVAILABLE


class GpuAssetUpdate(BaseModel):
    server_id: str | None = None
    gpu_id: str | None = Field(default=None, max_length=64)
    manufacturer: str | None = Field(default=None, max_length=128)
    model: str | None = Field(default=None, max_length=64)
    memory_gb: int | None = None
    serial_number: str | None = Field(default=None, max_length=128)
    acquisition_cost: Decimal | None = None
    acquisition_date: date | None = None
    supplier: str | None = Field(default=None, max_length=255)
    warranty: str | None = Field(default=None, max_length=128)
    operational_status: OperationalStatus | None = None
    commercial_status: CommercialStatus | None = None


class GpuAssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    server_id: str
    gpu_id: str
    manufacturer: str | None
    model: str
    memory_gb: int | None
    serial_number: str | None
    acquisition_cost: Decimal | None
    acquisition_date: date | None
    supplier: str | None
    warranty: str | None
    operational_status: OperationalStatus
    commercial_status: CommercialStatus
    created_at: datetime
    updated_at: datetime
