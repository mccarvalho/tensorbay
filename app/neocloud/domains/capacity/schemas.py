"""Pydantic v2 schemas for the Capacity Management module."""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ProcurementStatus(StrEnum):
    NEGOTIATING = "NEGOTIATING"
    ORDERED = "ORDERED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    OPERATIONAL = "OPERATIONAL"


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


class ListedAvailability(BaseModel):
    """One line of the Capacity page's availability list that matches the requested platform."""

    site: str
    gpu_model: str
    cooling: str | None = None
    available_from: date | None = None  # null = immediate
    gpus: int                           # racks are converted to GPUs (72 per NVL72 rack)
    racks: int | None = None


class AvailabilityCheck(BaseModel):
    """Result of an overselling-prevention check (plan section 9).

    ``available``/``incoming`` come from the asset inventory and supply orders. ``listed_now`` and
    ``listed_later`` come from the availability list on the Capacity page (what sales can offer),
    and count toward the status: immediate entries like stock, dated entries like incoming supply.
    """

    gpu_model: str
    requested: int
    available: int
    gap: int
    incoming: int
    status: AvailabilityStatus
    listed_now: int = 0
    listed_later: int = 0
    listed: list[ListedAvailability] = []


# --- Incoming capacity ---
class IncomingCapacityCreate(BaseModel):
    gpu_model: str = Field(..., max_length=64)
    quantity: int = Field(..., ge=0)
    supplier_id: str | None = Field(default=None, max_length=36)
    status: ProcurementStatus = ProcurementStatus.NEGOTIATING
    unit_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    expected_delivery: date | None = None
    expected_operational: date | None = None
    actual_delivery: date | None = None
    actual_operational: date | None = None
    purchase_order: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class IncomingCapacityUpdate(BaseModel):
    gpu_model: str | None = Field(default=None, max_length=64)
    quantity: int | None = Field(default=None, ge=0)
    supplier_id: str | None = Field(default=None, max_length=36)
    status: ProcurementStatus | None = None
    unit_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    expected_delivery: date | None = None
    expected_operational: date | None = None
    actual_delivery: date | None = None
    actual_operational: date | None = None
    purchase_order: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class IncomingCapacityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gpu_model: str
    quantity: int
    supplier_id: str | None
    status: ProcurementStatus
    unit_price: Decimal | None
    currency: str | None
    expected_delivery: date | None
    expected_operational: date | None
    actual_delivery: date | None
    actual_operational: date | None
    purchase_order: str | None
    notes: str | None
    order_id: str | None = None
    lot_label: str | None = None
    created_at: datetime
    updated_at: datetime


# --- Supply orders (GPU purchase contracts recorded by totals) ---
class LotInput(BaseModel):
    """A delivery lot. Give ``servers`` (x GPUs per server) or ``quantity`` (GPUs)."""

    label: str | None = Field(default=None, max_length=64)
    servers: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1)
    status: ProcurementStatus | None = None
    expected_delivery: date | None = None
    expected_operational: date | None = None
    actual_delivery: date | None = None
    actual_operational: date | None = None
    notes: str | None = None


class LotUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=64)
    servers: int | None = Field(default=None, ge=1)
    quantity: int | None = Field(default=None, ge=1)
    status: ProcurementStatus | None = None
    expected_delivery: date | None = None
    expected_operational: date | None = None
    actual_delivery: date | None = None
    actual_operational: date | None = None
    notes: str | None = None


class SupplyOrderBase(BaseModel):
    reference: str = Field(..., min_length=1, max_length=128)
    supplier_id: str | None = Field(default=None, max_length=36)
    supplier_quote: str | None = Field(default=None, max_length=128)
    status: ProcurementStatus = ProcurementStatus.ORDERED
    signed_on: date | None = None
    gpu_model: str = Field(..., min_length=1, max_length=64)
    server_model: str | None = Field(default=None, max_length=128)
    gpus_per_server: int = Field(default=8, ge=1, le=1024)
    servers: int = Field(..., ge=1, le=100_000)
    unit_price_per_server: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default="USD", max_length=3)
    payment_terms: str | None = None
    assembly_site: str | None = Field(default=None, max_length=255)
    destination_site: str | None = Field(default=None, max_length=255)
    tax_regime: str | None = Field(default=None, max_length=255)
    delivery_window: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class SupplyOrderCreate(SupplyOrderBase):
    # Contract total as written on the proposal; default = servers x unit price.
    total_value: Decimal | None = Field(default=None, ge=0)
    # Empty = one unscheduled lot holding the whole order.
    lots: list[LotInput] = Field(default_factory=list, max_length=200)


class SupplyOrderUpdate(BaseModel):
    reference: str | None = Field(default=None, min_length=1, max_length=128)
    supplier_id: str | None = Field(default=None, max_length=36)
    supplier_quote: str | None = Field(default=None, max_length=128)
    status: ProcurementStatus | None = None
    signed_on: date | None = None
    gpu_model: str | None = Field(default=None, min_length=1, max_length=64)
    server_model: str | None = Field(default=None, max_length=128)
    gpus_per_server: int | None = Field(default=None, ge=1, le=1024)
    servers: int | None = Field(default=None, ge=1, le=100_000)
    unit_price_per_server: Decimal | None = Field(default=None, ge=0)
    total_value: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    payment_terms: str | None = None
    assembly_site: str | None = Field(default=None, max_length=255)
    destination_site: str | None = Field(default=None, max_length=255)
    tax_regime: str | None = Field(default=None, max_length=255)
    delivery_window: str | None = Field(default=None, max_length=128)
    notes: str | None = None


class LotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    lot_label: str | None
    quantity: int
    servers: int | None = None
    status: ProcurementStatus
    expected_delivery: date | None
    expected_operational: date | None
    actual_delivery: date | None
    actual_operational: date | None
    notes: str | None


class SupplyOrderRead(SupplyOrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    gpus_total: int
    total_value: Decimal | None
    created_at: datetime
    updated_at: datetime
    # Derived from the lots.
    scheduled_gpus: int = 0
    unscheduled_gpus: int = 0
    unallocated_gpus: int = 0  # contracted but not in any lot yet
    delivered_gpus: int = 0
    operational_gpus: int = 0
    next_delivery: date | None = None
    lots: list[LotRead] = Field(default_factory=list)


class ForecastMonth(BaseModel):
    month: str  # YYYY-MM
    arriving: int
    cumulative: int


class ModelForecast(BaseModel):
    gpu_model: str
    contracted: int  # committed supply (ORDERED and later)
    negotiating: int  # pipeline only, not counted as contracted
    delivered: int
    operational: int
    unscheduled: int  # contracted, no date yet
    overdue: int  # expected before this month, not delivered yet
    months: list[ForecastMonth]


class SupplyForecast(BaseModel):
    start_month: str
    months: int
    models: list[ModelForecast]
