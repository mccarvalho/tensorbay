"""Capacity computation services (product plan sections 9 & 12).

The capacity ledger and overselling check read directly from the GPU asset
inventory so that commercial capacity is always derived from the real
physical state, never from a stale cached counter.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import re
from datetime import date

from neocloud.domains.capacity.models import (
    COMMITTED_PROCUREMENT_STATUSES,
    AvailabilityOffer,
    IncomingCapacity,
)
from neocloud.domains.capacity.schemas import (
    AvailabilityCheck,
    AvailabilityStatus,
    CapacityLedger,
    ListedAvailability,
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


GPUS_PER_RACK = 72  # GB200/GB300 NVL72 and VR200 racks
_PLATFORMS = ("GB300", "GB200", "VR200", "B300", "B200", "H200", "H100", "A100", "RTX6000")


def platform_of(gpu_model: str | None) -> str:
    """The platform a model name refers to, so "HGX B300 Liquid-Cooled", "B300" and "HGXB300" match."""
    m = re.sub(r"[^A-Z0-9]", "", (gpu_model or "").upper())
    if "VERARUBIN" in m:
        return "VR200"
    if "RTX" in m and "6000" in m:
        return "RTX6000"
    return next((p for p in _PLATFORMS if p in m), m)


def cooling_of(gpu_model: str | None) -> str | None:
    m = (gpu_model or "").upper()
    return "LIQUID" if "LIQUID" in m or "DLC" in m else "AIR" if "AIR" in m else None


async def listed_availability(session: AsyncSession, gpu_model: str) -> list[ListedAvailability]:
    """Lines of the availability list for this platform (and cooling, when the request names one)."""
    want, cool = platform_of(gpu_model), cooling_of(gpu_model)
    rows = (await session.execute(select(AvailabilityOffer))).scalars().all()
    out = []
    for o in rows:
        if platform_of(o.gpu_model) != want or o.available_qty <= 0:
            continue
        if cool and o.cooling and o.cooling != cool:
            continue
        racks = o.available_qty if o.quantity_unit == "RACKS" else None
        out.append(ListedAvailability(
            site=o.site, gpu_model=o.gpu_model, cooling=o.cooling, available_from=o.available_from,
            gpus=o.available_qty * GPUS_PER_RACK if racks is not None else o.available_qty, racks=racks,
        ))
    out.sort(key=lambda x: (x.available_from is not None, x.available_from or date.min, x.site))
    return out


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
    listed = await listed_availability(session, gpu_model)
    listed_now = sum(x.gpus for x in listed if x.available_from is None)
    listed_later = sum(x.gpus for x in listed if x.available_from is not None)
    now = available + listed_now
    gap = max(requested_qty - now, 0)

    if now >= requested_qty:
        availability_status = AvailabilityStatus.AVAILABLE
    elif now + incoming + listed_later >= requested_qty:
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
        listed_now=listed_now,
        listed_later=listed_later,
        listed=listed,
    )
