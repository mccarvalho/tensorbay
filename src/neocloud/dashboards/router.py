from typing import Annotated

from fastapi import APIRouter, Depends

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db

router = APIRouter()


# Note: Dashboards module has no models — it queries across other modules' tables


@router.get("/fleet")
async def fleet_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Fleet overview: total/operational/available/reserved/allocated GPUs by model and location."""
    ...


@router.get("/capacity")
async def capacity_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Capacity utilization dashboard with timeline."""
    ...


@router.get("/commercial")
async def commercial_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.read"))],
):
    """Commercial dashboard: active contracts, TCV, ARR, pipeline demand."""
    ...


@router.get("/executive")
async def executive_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("admin.*"))],
):
    """Executive KPI summary: GPUs, utilization, ARR, pipeline, capacity gap."""
    ...
