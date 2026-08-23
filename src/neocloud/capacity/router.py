import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db

router = APIRouter()


@router.get("/summary")
async def get_capacity_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    gpu_model: str | None = None,
    region: str | None = None,
):
    """Get current capacity summary (physical, operational, reserved, allocated, available)."""
    ...


@router.get("/timeline")
async def get_capacity_timeline(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    gpu_model: str | None = None,
    region: str | None = None,
    months_ahead: int = 6,
):
    """Get forward-looking capacity timeline."""
    ...


@router.get("/ledger")
async def get_capacity_ledger(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    gpu_model: str | None = None,
    region: str | None = None,
    limit: int = 50,
):
    """Get recent capacity ledger entries."""
    ...


@router.get("/incoming")
async def list_incoming_capacity(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    status: str | None = None,
):
    """List incoming capacity (purchase orders, deliveries)."""
    ...


@router.post("/incoming")
async def create_incoming_capacity(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Register incoming capacity (purchase order)."""
    ...


@router.get("/check")
async def check_capacity(
    gpu_model: str,
    quantity: int,
    region: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
    start_date: str | None = None,
    end_date: str | None = None,
):
    """Check if requested capacity is available."""
    ...
