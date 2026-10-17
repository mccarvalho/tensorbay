"""Executive / FinOps dashboard endpoints (product plan section 17)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.auth.dependencies import require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.dashboards import service
from neocloud.domains.dashboards.schemas import (
    CapacityByModel,
    CommercialKPIs,
    ExecutiveOverview,
    FinanceKPIs,
    FleetKPIs,
)

router = APIRouter(prefix="/dashboards", tags=["Dashboards"])

# Dashboards are read-only aggregations; capacity read is the baseline grant
# (SUPER_ADMIN/EXECUTIVE and most internal roles hold it).
_read = Depends(require_permission(Permission.CAPACITY_READ))


@router.get("/executive", response_model=ExecutiveOverview, dependencies=[_read])
async def executive_overview(
    session: AsyncSession = Depends(get_session),
) -> ExecutiveOverview:
    return await service.build_overview(session)


@router.get("/fleet", response_model=FleetKPIs, dependencies=[_read])
async def fleet(session: AsyncSession = Depends(get_session)) -> FleetKPIs:
    return await service._fleet(session)


@router.get(
    "/capacity", response_model=list[CapacityByModel], dependencies=[_read]
)
async def capacity(
    session: AsyncSession = Depends(get_session),
) -> list[CapacityByModel]:
    return await service._capacity_by_model(session)


@router.get("/commercial", response_model=CommercialKPIs, dependencies=[_read])
async def commercial(
    session: AsyncSession = Depends(get_session),
) -> CommercialKPIs:
    return await service._commercial(session)


@router.get("/finance", response_model=FinanceKPIs, dependencies=[_read])
async def finance(session: AsyncSession = Depends(get_session)) -> FinanceKPIs:
    return await service._finance(session)
