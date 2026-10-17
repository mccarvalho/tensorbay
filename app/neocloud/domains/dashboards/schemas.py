"""Executive / FinOps dashboard response schemas (product plan section 17)."""

from decimal import Decimal

from pydantic import BaseModel


class FleetKPIs(BaseModel):
    installed_gpus: int
    operational_gpus: int
    available_gpus: int
    reserved_gpus: int
    allocated_gpus: int
    maintenance_gpus: int
    offline_gpus: int
    failed_gpus: int
    failure_rate_pct: float


class CapacityByModel(BaseModel):
    gpu_model: str
    physical: int
    operational: int
    reserved: int
    allocated: int
    available: int
    incoming: int


class CommercialKPIs(BaseModel):
    contracted_gpus: int
    reserved_gpus: int
    active_contracts: int
    pipeline_gpu_demand: int
    weighted_pipeline_gpu_demand: float
    open_opportunities: int


class FinanceKPIs(BaseModel):
    mrr: Decimal
    arr: Decimal
    contracted_arr: Decimal
    revenue_backlog: Decimal
    weighted_pipeline_mrr: Decimal


class ExecutiveOverview(BaseModel):
    fleet: FleetKPIs
    capacity: list[CapacityByModel]
    commercial: CommercialKPIs
    finance: FinanceKPIs
