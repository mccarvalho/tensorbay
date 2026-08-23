import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db
from neocloud.common.pagination import PaginationParams

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_allocation(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.create"))],
):
    """Allocate specific GPUs to a reservation."""
    ...


@router.get("")
async def list_allocations(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    pagination: Annotated[PaginationParams, Depends()],
    reservation_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    gpu_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """List allocations with filters."""
    ...


@router.get("/{allocation_id}")
async def get_allocation(
    allocation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Get allocation details."""
    ...


@router.post("/{allocation_id}/release")
async def release_allocation(
    allocation_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.release"))],
):
    """Release an allocation — GPU returns to available."""
    ...


@router.post("/{allocation_id}/replace")
async def replace_gpu_in_allocation(
    allocation_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("allocation.create"))],
):
    """Replace a failed GPU in an allocation without changing the contract."""
    ...


@router.get("/history/gpu/{gpu_id}")
async def get_gpu_allocation_history(
    gpu_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Get allocation history for a specific GPU."""
    ...


@router.get("/history/customer/{customer_id}")
async def get_customer_allocation_history(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Get allocation history for a customer."""
    ...
