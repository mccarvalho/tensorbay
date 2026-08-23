import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db

router = APIRouter()


@router.post("/skus", status_code=status.HTTP_201_CREATED)
async def create_sku(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.write"))],
):
    """Create a new SKU."""
    ...


@router.get("/skus")
async def list_skus(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.read"))],
    category: str | None = None,
    is_active: bool = True,
):
    """List SKUs with optional filters."""
    ...


@router.post("/price-books", status_code=status.HTTP_201_CREATED)
async def create_price_book(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.write"))],
):
    """Create a price book."""
    ...


@router.get("/price-books")
async def list_price_books(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.read"))],
):
    """List all price books."""
    ...


@router.post("/price-books/{price_book_id}/entries", status_code=status.HTTP_201_CREATED)
async def add_price_entry(
    price_book_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.write"))],
):
    """Add a price entry to a price book."""
    ...


@router.get("/pricing/resolve")
async def resolve_price(
    sku_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("pricing.read"))],
    customer_id: uuid.UUID | None = None,
    contract_id: uuid.UUID | None = None,
    region: str | None = None,
):
    """Resolve the effective price for a SKU given context (customer, contract, region)."""
    ...
