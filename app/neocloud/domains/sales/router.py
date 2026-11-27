"""Sales & Opportunity router (prefix /sales).

Reads require CUSTOMER_READ; writes require CUSTOMER_WRITE. Every write is
recorded in the audit trail using the current user's subject as the actor.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.sales import models, schemas

router = APIRouter(prefix="/sales", tags=["Sales"])


# --------------------------------------------------------------------------- #
# Opportunities
# --------------------------------------------------------------------------- #


@router.get("/inventory-lanes", response_model=list[schemas.InventoryLane])
async def inventory_lanes(
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[schemas.InventoryLane]:
    """Per GPU model: stock, committed incoming supply and the demand of open deals.

    Lets sales see whether Procurement can cover a deal before promising it.
    """
    from neocloud.domains.capacity import service as capacity_service

    rows = await session.execute(
        select(models.Opportunity.gpu_model, func.coalesce(func.sum(models.Opportunity.quantity), 0))
        .where(models.Opportunity.sales_stage.in_([s.value for s in models.OPEN_STAGES]))
        .group_by(models.Opportunity.gpu_model)
    )
    demand = {m: int(q) for m, q in rows.all()}
    models_seen = set(demand) | set(
        (await session.execute(select(models.Opportunity.gpu_model).distinct())).scalars().all()
    )
    lanes = []
    for model in sorted(models_seen):
        ledger = await capacity_service.compute_ledger(session, model)
        incoming = await capacity_service._incoming_quantity(session, model)
        lanes.append(
            schemas.InventoryLane(
                gpu_model=model, physical=ledger.physical, allocated=ledger.allocated,
                reserved=ledger.reserved, available=ledger.available, incoming=incoming,
                open_demand=demand.get(model, 0),
            )
        )
    return lanes


@router.get("/opportunities", response_model=list[schemas.OpportunityRead])
async def list_opportunities(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[models.Opportunity]:
    result = await session.execute(
        select(models.Opportunity)
        .order_by(models.Opportunity.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.get("/opportunities/{opportunity_id}", response_model=schemas.OpportunityRead)
async def get_opportunity(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> models.Opportunity:
    obj = await session.get(models.Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    return obj


def _apply_minimum_order(obj: models.Opportunity, user: CurrentUser, *, quantity_changed: bool) -> None:
    """Orders under 32 servers (256 GPUs) need an administrator. An admin saving one approves it;
    anyone else leaves it PENDING. An approval holds until the quantity changes."""
    if obj.quantity >= models.MIN_ORDER_GPUS:
        obj.min_order_status = obj.min_order_approved_by = None
    elif user.has_permission(Permission.USER_ADMIN):
        obj.min_order_status, obj.min_order_approved_by = "APPROVED", user.email or user.subject
    elif quantity_changed or obj.min_order_status is None:
        obj.min_order_status, obj.min_order_approved_by = "PENDING", None


def _check_stage_allowed(obj: models.Opportunity, stage) -> None:  # noqa: ANN001
    if obj.min_order_status == "PENDING" and str(getattr(stage, "value", stage)) not in models.STAGES_WITHOUT_APPROVAL:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"This order is below the minimum of {models.MIN_ORDER_SERVERS} servers ({models.MIN_ORDER_GPUS} GPUs). "
            "An administrator must approve it before it moves past the proposal.",
        )


@router.post("/opportunities/{opportunity_id}/approve-minimum", response_model=schemas.OpportunityRead)
async def approve_minimum_order(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.USER_ADMIN)),
) -> models.Opportunity:
    """An administrator accepts an order below the minimum size."""
    obj = await session.get(models.Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    if obj.min_order_status is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This order meets the minimum; nothing to approve")
    obj.min_order_status, obj.min_order_approved_by = "APPROVED", user.email or user.subject
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="approve_minimum_order", entity_type="Opportunity", entity_id=obj.id, actor=user.subject,
        new_value={"quantity": obj.quantity},
    )
    await session.refresh(obj)
    return obj


@router.post(
    "/opportunities",
    response_model=schemas.OpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_opportunity(
    payload: schemas.OpportunityCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> models.Opportunity:
    obj = models.Opportunity(
        **payload.model_dump(),
        tenant_id=user.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    _apply_minimum_order(obj, user, quantity_changed=True)
    _check_stage_allowed(obj, obj.sales_stage)
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Opportunity",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/opportunities/{opportunity_id}", response_model=schemas.OpportunityRead)
async def update_opportunity(
    opportunity_id: str,
    payload: schemas.OpportunityUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> models.Opportunity:
    obj = await session.get(models.Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")

    changes = payload.model_dump(exclude_unset=True)
    old_quantity = obj.quantity
    # Moving a deal to another stage (e.g. dragging it on the board) resets its
    # probability to that stage's default, unless the caller set one explicitly.
    new_stage = changes.get("sales_stage")
    escrow = changes.get("escrow_required", obj.escrow_required)
    if new_stage is not None and new_stage != obj.sales_stage:
        stage = models.SalesStage(new_stage)
        if stage in models.ESCROW_STAGES and not escrow:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "This deal has no escrow account; the Payment substages do not apply",
            )
        if stage == models.SalesStage.ON_HOLD:
            # Remember where it was so it can be resumed; keep its probability.
            changes["stage_before_hold"] = obj.sales_stage
        else:
            if obj.sales_stage == models.SalesStage.ON_HOLD:
                changes["stage_before_hold"] = None
            if "probability" not in changes:
                changes["probability"] = models.STAGE_PROBABILITY[stage]
    for field, value in changes.items():
        setattr(obj, field, value)
    _apply_minimum_order(obj, user, quantity_changed="quantity" in changes and changes["quantity"] != old_quantity)
    if "sales_stage" in changes:
        _check_stage_allowed(obj, changes["sales_stage"])
    obj.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Opportunity",
        entity_id=obj.id,
        actor=user.subject,
        new_value={
            **payload.model_dump(mode="json", exclude_unset=True),
            **({"probability": changes["probability"]} if "probability" in changes else {}),
        },
    )
    await session.refresh(obj)
    return obj


@router.delete("/opportunities/{opportunity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_opportunity(
    opportunity_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> None:
    obj = await session.get(models.Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="Opportunity",
        entity_id=opportunity_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Quotes
# --------------------------------------------------------------------------- #


@router.get("/quotes", response_model=list[schemas.QuoteRead])
async def list_quotes(
    opportunity_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[models.Quote]:
    stmt = (
        select(models.Quote)
        .options(selectinload(models.Quote.items))
        .order_by(models.Quote.created_at.desc())
    )
    if opportunity_id is not None:
        stmt = stmt.where(models.Quote.opportunity_id == opportunity_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/quotes/{quote_id}", response_model=schemas.QuoteRead)
async def get_quote(
    quote_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> models.Quote:
    result = await session.execute(
        select(models.Quote)
        .options(selectinload(models.Quote.items))
        .where(models.Quote.id == quote_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    return obj


@router.post(
    "/quotes", response_model=schemas.QuoteRead, status_code=status.HTTP_201_CREATED
)
async def create_quote(
    payload: schemas.QuoteCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> models.Quote:
    opportunity = await session.get(models.Opportunity, payload.opportunity_id)
    if opportunity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")

    data = payload.model_dump(exclude={"items"})
    obj = models.Quote(
        **data,
        tenant_id=user.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    for item in payload.items:
        obj.items.append(
            models.QuoteItem(
                **item.model_dump(), created_by=user.subject, updated_by=user.subject
            )
        )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Quote",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    result = await session.execute(
        select(models.Quote)
        .options(selectinload(models.Quote.items))
        .where(models.Quote.id == obj.id)
    )
    return result.scalar_one()


@router.patch("/quotes/{quote_id}", response_model=schemas.QuoteRead)
async def update_quote(
    quote_id: str,
    payload: schemas.QuoteUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> models.Quote:
    obj = await session.get(models.Quote, quote_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(obj, field, value)
    obj.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Quote",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    result = await session.execute(
        select(models.Quote)
        .options(selectinload(models.Quote.items))
        .where(models.Quote.id == obj.id)
    )
    return result.scalar_one()


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quote(
    quote_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> None:
    obj = await session.get(models.Quote, quote_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Quote not found")
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="Quote",
        entity_id=quote_id,
        actor=user.subject,
    )
