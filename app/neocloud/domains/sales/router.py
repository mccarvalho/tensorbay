"""Sales & Opportunity router (prefix /sales).

Reads require CUSTOMER_READ; writes require CUSTOMER_WRITE. Every write is
recorded in the audit trail using the current user's subject as the actor.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
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
    for field, value in changes.items():
        setattr(obj, field, value)
    obj.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Opportunity",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
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
