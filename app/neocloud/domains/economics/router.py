"""Economics & Commissions API - Phase 1 (Reps + Commission Plans).

Reads require ECONOMICS_READ, writes require ECONOMICS_WRITE. Every write is
recorded in the audit trail. Deal approval and commission calculation arrive in
later phases.
"""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import get_settings
from neocloud.core.logging import get_logger
from neocloud.db.session import get_session
from neocloud.domains.economics import service as economics_service
from neocloud.domains.economics.models import (
    CommissionDeal,
    CommissionPlan,
    CommissionRun,
    CommissionStatement,
    CostItem,
    DealStatus,
    PaymentStatus,
    RunStatus,
    RepType,
    SalesRep,
)
from neocloud.domains.economics.schemas import (
    CommissionDealApprove,
    CommissionDealCreate,
    CommissionDealFromOpportunity,
    CommissionDealRead,
    CommissionDealReject,
    CommissionDealUpdate,
    CommissionPlanCreate,
    CommissionPlanRead,
    CommissionPlanUpdate,
    CommissionRunCreate,
    CommissionRunDetail,
    CommissionRunRead,
    CommissionStatementRead,
    CostItemCreate,
    CostItemRead,
    CostItemUpdate,
    DealEconomics,
    SalesRepCreate,
    SalesRepRead,
    SalesRepUpdate,
    StatementMarkPaid,
)
from neocloud.domains.sales.models import Opportunity

logger = get_logger(__name__)

router = APIRouter(prefix="/economics", tags=["Economics"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.ECONOMICS_READ))]
WriteUser = Annotated[
    CurrentUser, Depends(require_permission(Permission.ECONOMICS_WRITE))
]
ApproveUser = Annotated[
    CurrentUser, Depends(require_permission(Permission.COMMISSION_APPROVE))
]
Session = Annotated[AsyncSession, Depends(get_session)]

ENTITY_REP = "sales_rep"
ENTITY_PLAN = "commission_plan"
ENTITY_DEAL = "commission_deal"


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
    # Guard: don't orphan deals that credit this rep.
    in_use = await session.execute(
        select(CommissionDeal.id)
        .where(
            (CommissionDeal.ae_id == rep_id)
            | (CommissionDeal.am_id == rep_id)
            | (CommissionDeal.finder_id == rep_id)
        )
        .limit(1)
    )
    if in_use.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rep is referenced by one or more commission deals; set INACTIVE instead of deleting",
        )
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


# --------------------------------------------------------------------------- #
# Commission deals (Phase 2) - approval workflow + margin guardrail
# --------------------------------------------------------------------------- #
async def _get_deal_or_404(session: AsyncSession, deal_id: str) -> CommissionDeal:
    obj = await session.get(CommissionDeal, deal_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CommissionDeal {deal_id} not found",
        )
    return obj


async def _active_plan_for_year(
    session: AsyncSession, year: int
) -> CommissionPlan | None:
    result = await session.execute(
        select(CommissionPlan)
        .where(CommissionPlan.plan_year == year, CommissionPlan.is_active.is_(True))
        .order_by(CommissionPlan.created_at.desc())
    )
    return result.scalars().first()


def _is_privileged(user: CurrentUser) -> bool:
    """Execs/finance/super-admin see all deals; plain SALES see only their own."""
    privileged = {"SUPER_ADMIN", "EXECUTIVE", "FINANCE", "SALES_MANAGER"}
    return bool(privileged.intersection(set(user.roles or [])))


async def _rep_ids_for_user(session: AsyncSession, user: CurrentUser) -> list[str]:
    """SalesRep ids linked to this user's cognito sub (for own-deal scoping)."""
    result = await session.execute(
        select(SalesRep.id).where(SalesRep.cognito_sub == user.subject)
    )
    return [r for r in result.scalars().all()]


async def _recompute(session: AsyncSession, deal: CommissionDeal) -> None:
    deal.gross_profit = economics_service.gross_profit(deal.arr, deal.margin_pct)


@router.get("/deals", response_model=list[CommissionDealRead])
async def list_deals(
    session: Session,
    user: ReadUser,
    status_filter: DealStatus | None = Query(default=None, alias="status"),
    plan_year: int | None = None,
    customer_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(CommissionDeal).order_by(CommissionDeal.booked_date.desc())
    if status_filter:
        stmt = stmt.where(CommissionDeal.status == status_filter)
    if plan_year:
        stmt = stmt.where(CommissionDeal.plan_year == plan_year)
    if customer_id:
        stmt = stmt.where(CommissionDeal.customer_id == customer_id)
    # Rep-scoping: non-privileged users only see deals they are credited on.
    if not _is_privileged(user):
        rep_ids = await _rep_ids_for_user(session, user)
        if not rep_ids:
            return []
        stmt = stmt.where(
            CommissionDeal.ae_id.in_(rep_ids)
            | CommissionDeal.am_id.in_(rep_ids)
            | CommissionDeal.finder_id.in_(rep_ids)
        )
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/deals/{deal_id}", response_model=CommissionDealRead)
async def get_deal(deal_id: str, session: Session, user: ReadUser):
    deal = await _get_deal_or_404(session, deal_id)
    if not _is_privileged(user):
        rep_ids = await _rep_ids_for_user(session, user)
        if deal.ae_id not in rep_ids and deal.am_id not in rep_ids and deal.finder_id not in rep_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your deal")
    return deal


async def _build_deal(
    session: AsyncSession,
    *,
    name: str,
    customer_id: str,
    opportunity_id: str | None,
    arr_type,
    arr: Decimal,
    margin_pct,
    ae_id,
    am_id,
    is_referred,
    finder_id,
    booked_date,
    notes,
    actor: str,
) -> CommissionDeal:
    year = booked_date.year
    plan = await _active_plan_for_year(session, year)
    default_margin = plan.default_margin_pct if plan else None
    eff_margin = margin_pct if margin_pct is not None else (default_margin if default_margin is not None else Decimal("0.30"))
    deal = CommissionDeal(
        name=name,
        customer_id=customer_id,
        opportunity_id=opportunity_id,
        plan_id=plan.id if plan else None,
        arr_type=arr_type,
        arr=arr,
        margin_pct=eff_margin,
        ae_id=ae_id,
        am_id=am_id,
        is_referred=is_referred,
        finder_id=finder_id,
        booked_date=booked_date,
        plan_year=year,
        status=DealStatus.PENDING_APPROVAL,
        notes=notes,
        created_by=actor,
        updated_by=actor,
    )
    deal.gross_profit = economics_service.gross_profit(deal.arr, deal.margin_pct)
    # Margin guardrail flag (vs the plan default, or 30% fallback).
    threshold = default_margin if default_margin is not None else Decimal("0.30")
    deal.margin_warning = deal.margin_pct < threshold
    return deal


@router.post(
    "/deals", response_model=CommissionDealRead, status_code=status.HTTP_201_CREATED
)
async def create_deal(payload: CommissionDealCreate, session: Session, user: WriteUser):
    deal = await _build_deal(
        session,
        name=payload.name,
        customer_id=payload.customer_id,
        opportunity_id=payload.opportunity_id,
        arr_type=payload.arr_type,
        arr=payload.arr,
        margin_pct=payload.margin_pct,
        ae_id=payload.ae_id,
        am_id=payload.am_id,
        is_referred=payload.is_referred,
        finder_id=payload.finder_id,
        booked_date=payload.booked_date,
        notes=payload.notes,
        actor=user.subject,
    )
    session.add(deal)
    await session.flush()
    await record_audit(
        session, action="create", entity_type=ENTITY_DEAL, entity_id=deal.id,
        actor=user.subject, new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(deal)
    return deal


@router.post(
    "/deals/from-opportunity",
    response_model=CommissionDealRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_deal_from_opportunity(
    payload: CommissionDealFromOpportunity, session: Session, user: WriteUser
):
    opp = await session.get(Opportunity, payload.opportunity_id)
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp.sales_stage != "WON":
        raise HTTPException(
            status_code=400, detail="Only WON opportunities can become commission deals"
        )
    from datetime import date as _date

    arr = payload.arr if payload.arr is not None else economics_service.annualize_mrr(opp.expected_mrr)
    booked = payload.booked_date or _date.today()
    deal = await _build_deal(
        session,
        name=f"{opp.gpu_model} x{opp.quantity} ({opp.customer_id})",
        customer_id=opp.customer_id,
        opportunity_id=opp.id,
        arr_type=payload.arr_type,
        arr=arr,
        margin_pct=payload.margin_pct,
        ae_id=payload.ae_id,
        am_id=payload.am_id,
        is_referred=payload.is_referred,
        finder_id=payload.finder_id,
        booked_date=booked,
        notes=payload.notes,
        actor=user.subject,
    )
    session.add(deal)
    await session.flush()
    await record_audit(
        session, action="create", entity_type=ENTITY_DEAL, entity_id=deal.id,
        actor=user.subject, new_value={"opportunity_id": opp.id, "arr": str(arr)},
    )
    await session.refresh(deal)
    return deal


@router.patch("/deals/{deal_id}", response_model=CommissionDealRead)
async def update_deal(
    deal_id: str, payload: CommissionDealUpdate, session: Session, user: WriteUser
):
    deal = await _get_deal_or_404(session, deal_id)
    if deal.status != DealStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=409, detail="Only pending deals can be edited"
        )
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(deal, key, value)
    deal.updated_by = user.subject
    await _recompute(session, deal)
    plan = await _active_plan_for_year(session, deal.plan_year)
    threshold = plan.default_margin_pct if plan else Decimal("0.30")
    deal.margin_warning = deal.margin_pct < threshold
    await session.flush()
    await record_audit(
        session, action="update", entity_type=ENTITY_DEAL, entity_id=deal.id,
        actor=user.subject, new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(deal)
    return deal


@router.post("/deals/{deal_id}/approve", response_model=CommissionDealRead)
async def approve_deal(
    deal_id: str, payload: CommissionDealApprove, session: Session, user: ApproveUser
):
    from datetime import datetime, timezone

    deal = await _get_deal_or_404(session, deal_id)
    if deal.status != DealStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Deal is not pending approval")

    # Super Admin may adjust rate-relevant fields at approval.
    if payload.margin_pct is not None:
        deal.margin_pct = payload.margin_pct
    if payload.is_referred is not None:
        deal.is_referred = payload.is_referred
    if payload.finder_id is not None:
        deal.finder_id = payload.finder_id
    await _recompute(session, deal)

    plan = await _active_plan_for_year(session, deal.plan_year)
    threshold = plan.default_margin_pct if plan else Decimal("0.30")
    deal.margin_warning = deal.margin_pct < threshold

    # Guardrail: a sub-default-margin deal must be explicitly acknowledged, and
    # we alert the AM + configured Super Admin/finance recipients.
    if deal.margin_warning and not payload.acknowledge_margin_warning:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Margin {deal.margin_pct} is below plan default {threshold}; "
                "re-submit approval with acknowledge_margin_warning=true"
            ),
        )

    if deal.margin_warning:
        settings = get_settings()
        recipients: list[str] = []
        if deal.am_id:
            am = await session.get(SalesRep, deal.am_id)
            if am and am.email:
                recipients.append(am.email)
        recipients += [
            e.strip() for e in settings.economics_alert_emails.split(",") if e.strip()
        ]
        economics_service.send_margin_warning_email(
            settings,
            deal_name=deal.name,
            customer_id=deal.customer_id,
            arr=deal.arr,
            margin_pct=deal.margin_pct,
            default_margin_pct=threshold,
            recipients=sorted(set(recipients)),
        )

    deal.status = DealStatus.APPROVED
    deal.approved_by = user.subject
    deal.approved_at = datetime.now(timezone.utc)
    deal.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="approve", entity_type=ENTITY_DEAL, entity_id=deal.id,
        actor=user.subject,
        new_value={"margin_pct": str(deal.margin_pct), "margin_warning": deal.margin_warning},
    )
    await session.refresh(deal)
    return deal


@router.post("/deals/{deal_id}/reject", response_model=CommissionDealRead)
async def reject_deal(
    deal_id: str, payload: CommissionDealReject, session: Session, user: ApproveUser
):
    deal = await _get_deal_or_404(session, deal_id)
    if deal.status != DealStatus.PENDING_APPROVAL:
        raise HTTPException(status_code=409, detail="Deal is not pending approval")
    deal.status = DealStatus.REJECTED
    deal.rejection_reason = payload.reason
    deal.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="reject", entity_type=ENTITY_DEAL, entity_id=deal.id,
        actor=user.subject, new_value={"reason": payload.reason},
    )
    await session.refresh(deal)
    return deal


# --------------------------------------------------------------------------- #
# Commission runs & statements (Phase 3) - quarterly calculation + payout
# --------------------------------------------------------------------------- #
async def _get_run_or_404(session: AsyncSession, run_id: str) -> CommissionRun:
    obj = await session.get(CommissionRun, run_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CommissionRun {run_id} not found",
        )
    return obj


@router.post(
    "/runs", response_model=CommissionRunDetail, status_code=status.HTTP_201_CREATED
)
async def create_run(payload: CommissionRunCreate, session: Session, user: WriteUser):
    """Calculate a quarterly commission run (annual gate, quarterly true-up)."""
    plan = await _active_plan_for_year(session, payload.plan_year)
    if plan is None:
        raise HTTPException(
            status_code=400,
            detail=f"No active commission plan for {payload.plan_year}",
        )

    # Approved deals for the plan year.
    deals = (
        await session.execute(
            select(CommissionDeal).where(
                CommissionDeal.plan_year == payload.plan_year,
                CommissionDeal.status == DealStatus.APPROVED,
            )
        )
    ).scalars().all()
    reps = (await session.execute(select(SalesRep))).scalars().all()

    # Prior-quarter paid amounts this year, keyed by (rep_id, component).
    prior_rows = (
        await session.execute(
            select(
                CommissionStatement.rep_id,
                CommissionStatement.component,
                CommissionStatement.amount,
            ).where(
                CommissionStatement.plan_year == payload.plan_year,
                CommissionStatement.quarter < payload.quarter,
            )
        )
    ).all()
    prior_paid_by_key: dict[tuple[str, str], Decimal] = {}
    for rep_id, component, amount in prior_rows:
        key = (rep_id, component.value if hasattr(component, "value") else str(component))
        prior_paid_by_key[key] = prior_paid_by_key.get(key, Decimal("0")) + Decimal(amount)

    lines = economics_service.compute_quarter_lines(
        plan=plan,
        reps=list(reps),
        approved_deals=list(deals),
        quarter=payload.quarter,
        prior_paid_by_key=prior_paid_by_key,
    )

    run = CommissionRun(
        plan_year=payload.plan_year,
        quarter=payload.quarter,
        plan_id=plan.id,
        status=RunStatus.DRAFT,
        notes=payload.notes,
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(run)
    await session.flush()

    total = Decimal("0")
    for ln in lines:
        stmt = CommissionStatement(
            run_id=run.id,
            rep_id=ln.rep_id,
            component=ln.component,
            plan_year=payload.plan_year,
            quarter=payload.quarter,
            ytd_arr=ln.ytd_arr,
            quota_arr=ln.quota_arr,
            gate_cleared=ln.gate_cleared,
            rate=ln.rate,
            ytd_gross_profit=ln.ytd_gross_profit,
            ytd_earned=ln.ytd_earned,
            prior_paid=ln.prior_paid,
            amount=ln.amount,
            created_by=user.subject,
            updated_by=user.subject,
        )
        session.add(stmt)
        total += ln.amount
    run.total_commission = total.quantize(Decimal("0.01"))
    await session.flush()
    await record_audit(
        session, action="create", entity_type="commission_run", entity_id=run.id,
        actor=user.subject,
        new_value={"plan_year": payload.plan_year, "quarter": payload.quarter, "total": str(run.total_commission)},
    )

    statements = (
        await session.execute(
            select(CommissionStatement).where(CommissionStatement.run_id == run.id)
        )
    ).scalars().all()
    await session.refresh(run)
    detail = CommissionRunDetail.model_validate(run)
    detail.statements = [CommissionStatementRead.model_validate(s) for s in statements]
    return detail


@router.get("/runs", response_model=list[CommissionRunRead])
async def list_runs(
    session: Session,
    _user: ReadUser,
    plan_year: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(CommissionRun).order_by(
        CommissionRun.plan_year.desc(), CommissionRun.quarter.desc()
    )
    if plan_year:
        stmt = stmt.where(CommissionRun.plan_year == plan_year)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/runs/{run_id}", response_model=CommissionRunDetail)
async def get_run(run_id: str, session: Session, user: ReadUser):
    run = await _get_run_or_404(session, run_id)
    stmt = select(CommissionStatement).where(CommissionStatement.run_id == run_id)
    # Rep-scoping: non-privileged users only see their own statement lines.
    if not _is_privileged(user):
        rep_ids = await _rep_ids_for_user(session, user)
        if not rep_ids:
            detail = CommissionRunDetail.model_validate(run)
            detail.statements = []
            return detail
        stmt = stmt.where(CommissionStatement.rep_id.in_(rep_ids))
    statements = (await session.execute(stmt)).scalars().all()
    detail = CommissionRunDetail.model_validate(run)
    detail.statements = [CommissionStatementRead.model_validate(s) for s in statements]
    return detail


@router.post("/runs/{run_id}/finalize", response_model=CommissionRunRead)
async def finalize_run(run_id: str, session: Session, user: ApproveUser):
    run = await _get_run_or_404(session, run_id)
    if run.status == RunStatus.FINALIZED:
        raise HTTPException(status_code=409, detail="Run already finalized")
    run.status = RunStatus.FINALIZED
    run.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="finalize", entity_type="commission_run", entity_id=run.id,
        actor=user.subject,
    )
    await session.refresh(run)
    return run


@router.post(
    "/statements/{statement_id}/mark-paid", response_model=CommissionStatementRead
)
async def mark_statement_paid(
    statement_id: str, payload: StatementMarkPaid, session: Session, user: WriteUser
):
    from datetime import datetime, timezone

    stmt = await session.get(CommissionStatement, statement_id)
    if stmt is None:
        raise HTTPException(status_code=404, detail="Statement not found")
    stmt.payment_status = PaymentStatus.PAID
    stmt.paid_at = datetime.now(timezone.utc)
    stmt.payment_reference = payload.payment_reference
    stmt.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="mark_paid", entity_type="commission_statement",
        entity_id=statement_id, actor=user.subject,
        new_value={"payment_reference": payload.payment_reference},
    )
    await session.refresh(stmt)
    return stmt


# --------------------------------------------------------------------------- #
# Cost items (Phase 4) - total-cost tracking + real margin
# --------------------------------------------------------------------------- #
ENTITY_COST = "cost_item"


async def _get_cost_or_404(session: AsyncSession, cost_id: str) -> CostItem:
    obj = await session.get(CostItem, cost_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"CostItem {cost_id} not found"
        )
    return obj


@router.get("/costs", response_model=list[CostItemRead])
async def list_costs(
    session: Session,
    _user: ReadUser,
    category: str | None = None,
    customer_id: str | None = None,
    deal_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(CostItem).order_by(CostItem.created_at.desc())
    if category:
        stmt = stmt.where(CostItem.category == category)
    if customer_id:
        stmt = stmt.where(CostItem.customer_id == customer_id)
    if deal_id:
        stmt = stmt.where(CostItem.deal_id == deal_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/costs/{cost_id}", response_model=CostItemRead)
async def get_cost(cost_id: str, session: Session, _user: ReadUser):
    return await _get_cost_or_404(session, cost_id)


@router.post("/costs", response_model=CostItemRead, status_code=status.HTTP_201_CREATED)
async def create_cost(payload: CostItemCreate, session: Session, user: WriteUser):
    obj = CostItem(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session, action="create", entity_type=ENTITY_COST, entity_id=obj.id,
        actor=user.subject, new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/costs/{cost_id}", response_model=CostItemRead)
async def update_cost(
    cost_id: str, payload: CostItemUpdate, session: Session, user: WriteUser
):
    obj = await _get_cost_or_404(session, cost_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="update", entity_type=ENTITY_COST, entity_id=obj.id,
        actor=user.subject, new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/costs/{cost_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cost(cost_id: str, session: Session, user: WriteUser):
    obj = await _get_cost_or_404(session, cost_id)
    await session.delete(obj)
    await record_audit(
        session, action="delete", entity_type=ENTITY_COST, entity_id=cost_id,
        actor=user.subject,
    )


@router.get("/deals/{deal_id}/economics", response_model=DealEconomics)
async def deal_economics(deal_id: str, session: Session, user: ReadUser):
    """Real margin for a deal: nominal (ARR x margin) vs. actual allocated cost.

    Real gross profit = ARR - allocated cost; real margin = real GP / ARR.
    """
    deal = await _get_deal_or_404(session, deal_id)
    if not _is_privileged(user):
        rep_ids = await _rep_ids_for_user(session, user)
        if deal.ae_id not in rep_ids and deal.am_id not in rep_ids and deal.finder_id not in rep_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your deal")
    cost_rows = (
        await session.execute(
            select(CostItem.amount).where(CostItem.deal_id == deal_id)
        )
    ).scalars().all()
    allocated = sum((Decimal(c) for c in cost_rows), Decimal("0")).quantize(Decimal("0.01"))
    real_gp = (Decimal(deal.arr) - allocated).quantize(Decimal("0.01"))
    real_margin = (
        (real_gp / Decimal(deal.arr)).quantize(Decimal("0.0001"))
        if deal.arr and Decimal(deal.arr) != 0
        else None
    )
    return DealEconomics(
        deal_id=deal.id,
        arr=deal.arr,
        nominal_margin_pct=deal.margin_pct,
        nominal_gross_profit=deal.gross_profit,
        allocated_cost=allocated,
        real_gross_profit=real_gp,
        real_margin_pct=real_margin,
    )
