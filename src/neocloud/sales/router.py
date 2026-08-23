import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db
from neocloud.common.pagination import PaginationParams

router = APIRouter()


@router.post("/opportunities", status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Create a new sales opportunity."""
    ...


@router.get("/opportunities")
async def list_opportunities(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
    pagination: Annotated[PaginationParams, Depends()],
    stage: str | None = None,
    customer_id: uuid.UUID | None = None,
):
    """List opportunities with filters."""
    ...


@router.patch("/opportunities/{opportunity_id}")
async def update_opportunity(
    opportunity_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Update an opportunity (including stage transitions)."""
    ...


@router.post("/opportunities/{opportunity_id}/capacity-check", status_code=status.HTTP_201_CREATED)
async def request_capacity_check(
    opportunity_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("capacity.read"))],
):
    """Request a capacity availability check for an opportunity."""
    ...


@router.post("/opportunities/{opportunity_id}/quotes", status_code=status.HTTP_201_CREATED)
async def create_quote(
    opportunity_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Create a quote for an opportunity."""
    ...


@router.get("/quotes/{quote_id}")
async def get_quote(
    quote_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
):
    """Get quote details with line items."""
    ...


@router.post("/quotes/{quote_id}/accept")
async def accept_quote(
    quote_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Accept a quote — triggers contract creation."""
    ...
