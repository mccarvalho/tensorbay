"""Economics & Commissions API - Phase 1 (Reps + Commission Plans).

Reads require ECONOMICS_READ, writes require ECONOMICS_WRITE. Every write is
recorded in the audit trail. Deal approval and commission calculation arrive in
later phases.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.economics.models import CommissionPlan, RepType, SalesRep
from neocloud.domains.economics.schemas import (
    CommissionPlanCreate,
    CommissionPlanRead,
    CommissionPlanUpdate,
    SalesRepCreate,
    SalesRepRead,
    SalesRepUpdate,
)

router = APIRouter(prefix="/economics", tags=["Economics"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.ECONOMICS_READ))]
WriteUser = Annotated[
    CurrentUser, Depends(require_permission(Permission.ECONOMICS_WRITE))
]
Session = Annotated[AsyncSession, Depends(get_session)]

ENTITY_REP = "sales_rep"
ENTITY_PLAN = "commission_plan"


async def _get_rep_or_404(session: AsyncSession, rep_id: str) -> SalesRep:
    obj = await session.get(SalesRep, rep_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"SalesRep {rep_id} not found"
        )
    return obj


async def _get_plan_or_404(session: AsyncSession, plan_id: str) -> CommissionPlan:
    obj = await session.get(CommissionPlan, plan_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CommissionPlan {plan_id} not found",
        )
    return obj


# --------------------------------------------------------------------------- #
# Sales representatives / finders
# --------------------------------------------------------------------------- #
@router.get("/reps", response_model=list[SalesRepRead])
async def list_reps(
    session: Session,
    _user: ReadUser,
    q: str | None = None,
    type: RepType | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(SalesRep).order_by(SalesRep.name)
    if q:
        stmt = stmt.where(SalesRep.name.ilike(f"%{q}%"))
    if type:
        stmt = stmt.where(SalesRep.type == type)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/reps/{rep_id}", response_model=SalesRepRead)
async def get_rep(rep_id: str, session: Session, _user: ReadUser):
    return await _get_rep_or_404(session, rep_id)


@router.post("/reps", response_model=SalesRepRead, status_code=status.HTTP_201_CREATED)
async def create_rep(payload: SalesRepCreate, session: Session, user: WriteUser):
    obj = SalesRep(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_REP,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/reps/{rep_id}", response_model=SalesRepRead)
async def update_rep(
    rep_id: str, payload: SalesRepUpdate, session: Session, user: WriteUser
):
    obj = await _get_rep_or_404(session, rep_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_REP,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/reps/{rep_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rep(rep_id: str, session: Session, user: WriteUser):
    obj = await _get_rep_or_404(session, rep_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_REP,
        entity_id=rep_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Commission plans (versioned by year)
# --------------------------------------------------------------------------- #
@router.get("/plans", response_model=list[CommissionPlanRead])
async def list_plans(
    session: Session,
    _user: ReadUser,
    plan_year: int | None = None,
    active_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(CommissionPlan).order_by(CommissionPlan.plan_year.desc())
    if plan_year:
        stmt = stmt.where(CommissionPlan.plan_year == plan_year)
    if active_only:
        stmt = stmt.where(CommissionPlan.is_active.is_(True))
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/plans/{plan_id}", response_model=CommissionPlanRead)
async def get_plan(plan_id: str, session: Session, _user: ReadUser):
    return await _get_plan_or_404(session, plan_id)


@router.post(
    "/plans", response_model=CommissionPlanRead, status_code=status.HTTP_201_CREATED
)
async def create_plan(payload: CommissionPlanCreate, session: Session, user: WriteUser):
    obj = CommissionPlan(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_PLAN,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/plans/{plan_id}", response_model=CommissionPlanRead)
async def update_plan(
    plan_id: str, payload: CommissionPlanUpdate, session: Session, user: WriteUser
):
    obj = await _get_plan_or_404(session, plan_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_PLAN,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/plans/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: str, session: Session, user: WriteUser):
    obj = await _get_plan_or_404(session, plan_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_PLAN,
        entity_id=plan_id,
        actor=user.subject,
    )
