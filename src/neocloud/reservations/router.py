import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db
from neocloud.common.pagination import PaginationParams

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_reservation(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.create"))],
):
    """Create a reservation (usually triggered by contract activation)."""
    ...


@router.get("")
async def list_reservations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    pagination: Annotated[PaginationParams, Depends()],
    customer_id: uuid.UUID | None = None,
    contract_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """List reservations with filters."""
    ...


@router.get("/{reservation_id}")
async def get_reservation(
    reservation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Get reservation details."""
    ...


@router.post("/{reservation_id}/confirm")
async def confirm_reservation(
    reservation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.create"))],
):
    """Confirm a pending reservation."""
    ...


@router.post("/{reservation_id}/release")
async def release_reservation(
    reservation_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.release"))],
):
    """Release a reservation — returns capacity to available."""
    ...


@router.post("/{reservation_id}/cancel")
async def cancel_reservation(
    reservation_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.release"))],
):
    """Cancel a pending/confirmed reservation."""
    ...
