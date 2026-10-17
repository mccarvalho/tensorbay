"""FastAPI router for the Capacity Management module (prefix /capacity).

All reads require Permission.CAPACITY_READ. Incoming-capacity writes require
Permission.INVENTORY_WRITE (operations teams own future hardware records).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.capacity import schemas
from neocloud.domains.capacity.models import IncomingCapacity
from neocloud.domains.capacity.service import check_availability, compute_ledger

router = APIRouter(prefix="/capacity", tags=["Capacity"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.CAPACITY_READ))]
WriteUser = Annotated[CurrentUser, Depends(require_permission(Permission.INVENTORY_WRITE))]
Session = Annotated[AsyncSession, Depends(get_session)]
Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


# ---------------------------------------------------------------------------
# Capacity ledger and overselling check
# ---------------------------------------------------------------------------
@router.get("/ledger", response_model=schemas.CapacityLedger)
async def get_ledger(
    session: Session,
    _user: ReadUser,
    gpu_model: Annotated[str, Query(min_length=1)],
):
    return await compute_ledger(session, gpu_model)


@router.get("/check", response_model=schemas.AvailabilityCheck)
async def get_availability_check(
    session: Session,
    _user: ReadUser,
    gpu_model: Annotated[str, Query(min_length=1)],
    quantity: Annotated[int, Query(ge=1)],
):
    return await check_availability(session, gpu_model, quantity)


# ---------------------------------------------------------------------------
# Incoming capacity CRUD
# ---------------------------------------------------------------------------
async def _get_or_404(session: AsyncSession, entity_id: str) -> IncomingCapacity:
    obj = await session.get(IncomingCapacity, entity_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"IncomingCapacity {entity_id} not found",
        )
    return obj


@router.get("/incoming", response_model=list[schemas.IncomingCapacityRead])
async def list_incoming(
    session: Session,
    _user: ReadUser,
    gpu_model: str | None = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    stmt = select(IncomingCapacity)
    if gpu_model is not None:
        stmt = stmt.where(IncomingCapacity.gpu_model == gpu_model)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/incoming/{incoming_id}", response_model=schemas.IncomingCapacityRead)
async def get_incoming(incoming_id: str, session: Session, _user: ReadUser):
    return await _get_or_404(session, incoming_id)


@router.post(
    "/incoming",
    response_model=schemas.IncomingCapacityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_incoming(
    payload: schemas.IncomingCapacityCreate, session: Session, user: WriteUser
):
    obj = IncomingCapacity(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="capacity.incoming",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/incoming/{incoming_id}", response_model=schemas.IncomingCapacityRead)
async def update_incoming(
    incoming_id: str,
    payload: schemas.IncomingCapacityUpdate,
    session: Session,
    user: WriteUser,
):
    obj = await _get_or_404(session, incoming_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="capacity.incoming",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/incoming/{incoming_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incoming(incoming_id: str, session: Session, user: WriteUser):
    obj = await _get_or_404(session, incoming_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="capacity.incoming",
        entity_id=incoming_id,
        actor=user.subject,
    )
