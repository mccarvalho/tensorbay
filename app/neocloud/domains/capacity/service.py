"""Capacity computation services (product plan sections 9 & 12).

The capacity ledger and overselling check read directly from the GPU asset
inventory so that commercial capacity is always derived from the real
physical state, never from a stale cached counter.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.domains.capacity.models import (
    COMMITTED_PROCUREMENT_STATUSES,
    IncomingCapacity,
)
from neocloud.domains.capacity.schemas import (
    AvailabilityCheck,
    AvailabilityStatus,
    CapacityLedger,
)
from neocloud.domains.inventory.models import (
    CommercialStatus,
    GpuAsset,
    OperationalStatus,
)


async def compute_ledger(session: AsyncSession, gpu_model: str) -> CapacityLedger:
    """Build the capacity ledger for a GPU model from inventory counts.

    physical   = every GPU asset of this model
    offline    = operational_status OFFLINE
    maintenance= operational_status MAINTENANCE
    operational= operational_status ONLINE
    reserved   = commercial_status RESERVED
    allocated  = commercial_status ALLOCATED
    available  = operational - reserved - allocated (never below zero)
    """
    stmt = (
        select(
            func.count().label("physical"),
            func.count()
            .filter(GpuAsset.operational_status == OperationalStatus.OFFLINE)
            .label("offline"),
            func.count()
            .filter(GpuAsset.operational_status == OperationalStatus.MAINTENANCE)
            .label("maintenance"),
            func.count()
            .filter(GpuAsset.operational_status == OperationalStatus.ONLINE)
            .label("operational"),
            func.count()
            .filter(GpuAsset.commercial_status == CommercialStatus.RESERVED)
            .label("reserved"),
            func.count()
            .filter(GpuAsset.commercial_status == CommercialStatus.ALLOCATED)
            .label("allocated"),
        )
        .where(GpuAsset.model == gpu_model)
    )
    row = (await session.execute(stmt)).one()

    operational = row.operational or 0
    reserved = row.reserved or 0
    allocated = row.allocated or 0
    available = max(operational - reserved - allocated, 0)

    return CapacityLedger(
        gpu_model=gpu_model,
        physical=row.physical or 0,
        offline=row.offline or 0,
        maintenance=row.maintenance or 0,
        operational=operational,
        reserved=reserved,
        allocated=allocated,
        available=available,
    )


async def _incoming_quantity(session: AsyncSession, gpu_model: str) -> int:
    """Committed incoming supply only.

    NEGOTIATING records are pipeline-only (deals not yet closed) and must not
    count toward the overselling check; only ORDERED+ is committed supply.
    """
    stmt = select(func.coalesce(func.sum(IncomingCapacity.quantity), 0)).where(
        IncomingCapacity.gpu_model == gpu_model,
        IncomingCapacity.status.in_(
            [s.value for s in COMMITTED_PROCUREMENT_STATUSES]
        ),
    )
    return int((await session.execute(stmt)).scalar_one())


async def check_availability(
    session: AsyncSession, gpu_model: str, requested_qty: int
) -> AvailabilityCheck:
    """Overselling-prevention check for a requested quantity.

    AVAILABLE           -> current available capacity covers the request.
    PARTIALLY_AVAILABLE -> current capacity is short, but incoming capacity
                           closes the gap.
    UNAVAILABLE         -> even with incoming capacity the request cannot be met.
    """
    ledger = await compute_ledger(session, gpu_model)
    available = ledger.available
    incoming = await _incoming_quantity(session, gpu_model)
    gap = max(requested_qty - available, 0)

    if available >= requested_qty:
        availability_status = AvailabilityStatus.AVAILABLE
    elif available + incoming >= requested_qty:
        availability_status = AvailabilityStatus.PARTIALLY_AVAILABLE
    else:
        availability_status = AvailabilityStatus.UNAVAILABLE

    return AvailabilityCheck(
        gpu_model=gpu_model,
        requested=requested_qty,
        available=available,
        gap=gap,
        incoming=incoming,
        status=availability_status,
    )
