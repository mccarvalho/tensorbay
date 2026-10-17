"""Reservation & Allocation router (prefix /reservations).

Permission model (per plan section 13):
* read reservations/allocations      -> CAPACITY_READ
* create/update/delete reservation   -> CONTRACT_WRITE (commercial commitment)
* create an allocation               -> ALLOCATION_CREATE
* release an allocation              -> ALLOCATION_RELEASE

Reservation (commercial) and Allocation (physical) are kept as separate
entities. Every write is recorded in the audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.reservations import models, schemas

router = APIRouter(prefix="/reservations", tags=["Reservations"])

_RESERVATION_LOADER = selectinload(models.Reservation.allocations).selectinload(
    models.Allocation.gpus
)
_ALLOCATION_LOADER = selectinload(models.Allocation.gpus)


async def _get_reservation_full(
    session: AsyncSession, reservation_id: str
) -> models.Reservation:
    result = await session.execute(
        select(models.Reservation)
        .options(_RESERVATION_LOADER)
        .where(models.Reservation.id == reservation_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    return obj


async def _get_allocation_full(
    session: AsyncSession, allocation_id: str
) -> models.Allocation:
    result = await session.execute(
        select(models.Allocation)
        .options(_ALLOCATION_LOADER)
        .where(models.Allocation.id == allocation_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Allocation not found")
    return obj


# --------------------------------------------------------------------------- #
# Reservations (commercial commitment)
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[schemas.ReservationRead])
async def list_reservations(
    customer_id: str | None = Query(None),
    contract_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CAPACITY_READ)),
) -> list[models.Reservation]:
    stmt = (
        select(models.Reservation)
        .options(_RESERVATION_LOADER)
        .order_by(models.Reservation.created_at.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(models.Reservation.customer_id == customer_id)
    if contract_id is not None:
        stmt = stmt.where(models.Reservation.contract_id == contract_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/{reservation_id}", response_model=schemas.ReservationRead)
async def get_reservation(
    reservation_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CAPACITY_READ)),
) -> models.Reservation:
    return await _get_reservation_full(session, reservation_id)


@router.post("", response_model=schemas.ReservationRead, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    payload: schemas.ReservationCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.Reservation:
    obj = models.Reservation(
        **payload.model_dump(),
        tenant_id=user.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Reservation",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return await _get_reservation_full(session, obj.id)


@router.patch("/{reservation_id}", response_model=schemas.ReservationRead)
async def update_reservation(
    reservation_id: str,
    payload: schemas.ReservationUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.Reservation:
    obj = await session.get(models.Reservation, reservation_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    obj.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Reservation",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return await _get_reservation_full(session, reservation_id)


@router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reservation(
    reservation_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    obj = await session.get(models.Reservation, reservation_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="Reservation",
        entity_id=reservation_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Allocations (physical/logical binding)
# --------------------------------------------------------------------------- #


@router.get(
    "/{reservation_id}/allocations", response_model=list[schemas.AllocationRead]
)
async def list_allocations(
    reservation_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CAPACITY_READ)),
) -> list[models.Allocation]:
    # Ensure the reservation exists for a meaningful 404.
    exists = await session.get(models.Reservation, reservation_id)
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
    result = await session.execute(
        select(models.Allocation)
        .options(_ALLOCATION_LOADER)
        .where(models.Allocation.reservation_id == reservation_id)
        .order_by(models.Allocation.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/{reservation_id}/allocations",
    response_model=schemas.AllocationRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_allocation(
    reservation_id: str,
    payload: schemas.AllocationCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.ALLOCATION_CREATE)),
) -> models.Allocation:
    reservation = await session.get(models.Reservation, reservation_id)
    if reservation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")

    data = payload.model_dump(exclude={"gpu_asset_ids"})
    alloc = models.Allocation(
        reservation_id=reservation_id,
        **data,
        tenant_id=reservation.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    for gpu_asset_id in payload.gpu_asset_ids:
        alloc.gpus.append(
            models.AllocationGpu(
                gpu_asset_id=gpu_asset_id,
                created_by=user.subject,
                updated_by=user.subject,
            )
        )
    session.add(alloc)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Allocation",
        entity_id=alloc.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return await _get_allocation_full(session, alloc.id)


@router.patch(
    "/{reservation_id}/allocations/{allocation_id}",
    response_model=schemas.AllocationRead,
)
async def update_allocation(
    reservation_id: str,
    allocation_id: str,
    payload: schemas.AllocationUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.ALLOCATION_CREATE)),
) -> models.Allocation:
    alloc = await session.get(models.Allocation, allocation_id)
    if alloc is None or alloc.reservation_id != reservation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Allocation not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alloc, field, value)
    alloc.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Allocation",
        entity_id=alloc.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return await _get_allocation_full(session, allocation_id)


@router.post(
    "/{reservation_id}/allocations/{allocation_id}/release",
    response_model=schemas.AllocationRead,
)
async def release_allocation(
    reservation_id: str,
    allocation_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.ALLOCATION_RELEASE)),
) -> models.Allocation:
    alloc = await session.get(models.Allocation, allocation_id)
    if alloc is None or alloc.reservation_id != reservation_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Allocation not found")

    previous_status = alloc.status
    alloc.status = models.AllocationStatus.RELEASED
    alloc.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="release",
        entity_type="Allocation",
        entity_id=alloc.id,
        actor=user.subject,
        old_value={"status": str(previous_status)},
        new_value={"status": str(models.AllocationStatus.RELEASED)},
    )
    return await _get_allocation_full(session, allocation_id)
