"""Product Catalog & Pricing API (product plan EPIC 02 / section 8).

CRUD for SKUs, price books and prices under /catalog. Reads require
PRICING_READ, writes require PRICING_WRITE. Every write is audited.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.catalog.models import Price, PriceBook, Sku
from neocloud.domains.catalog.schemas import (
    PriceBookCreate,
    PriceBookResponse,
    PriceBookUpdate,
    PriceCreate,
    PriceResponse,
    PriceUpdate,
    SkuCreate,
    SkuResponse,
    SkuUpdate,
)

router = APIRouter(prefix="/catalog", tags=["Catalog"])

ENTITY_SKU = "sku"
ENTITY_PRICE_BOOK = "price_book"
ENTITY_PRICE = "price"


def _audit_old(instance, keys) -> dict[str, str]:
    return {k: str(getattr(instance, k)) for k in keys}


# --------------------------------------------------------------------------- #
# SKUs
# --------------------------------------------------------------------------- #


@router.get("/skus", response_model=list[SkuResponse])
async def list_skus(
    active: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> list[Sku]:
    stmt = select(Sku).order_by(Sku.code)
    if active is not None:
        stmt = stmt.where(Sku.active == active)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/skus/{sku_id}", response_model=SkuResponse)
async def get_sku(
    sku_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> Sku:
    sku = await session.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found"
        )
    return sku


@router.post(
    "/skus", response_model=SkuResponse, status_code=status.HTTP_201_CREATED
)
async def create_sku(
    payload: SkuCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> Sku:
    sku = Sku(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(sku)
    await session.flush()
    await session.refresh(sku)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_SKU,
        entity_id=sku.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return sku


@router.patch("/skus/{sku_id}", response_model=SkuResponse)
async def update_sku(
    sku_id: str,
    payload: SkuUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> Sku:
    sku = await session.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found"
        )
    changes = payload.model_dump(exclude_unset=True)
    old_value = _audit_old(sku, changes)
    for key, value in changes.items():
        setattr(sku, key, value)
    sku.updated_by = user.subject
    await session.flush()
    await session.refresh(sku)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_SKU,
        entity_id=sku.id,
        actor=user.subject,
        old_value=old_value,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return sku


@router.delete("/skus/{sku_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sku(
    sku_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> None:
    sku = await session.get(Sku, sku_id)
    if sku is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found"
        )
    await session.delete(sku)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_SKU,
        entity_id=sku_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Price books
# --------------------------------------------------------------------------- #


@router.get("/price-books", response_model=list[PriceBookResponse])
async def list_price_books(
    scope: str | None = Query(None),
    customer_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> list[PriceBook]:
    stmt = select(PriceBook).order_by(PriceBook.name)
    if scope is not None:
        stmt = stmt.where(PriceBook.scope == scope)
    if customer_id is not None:
        stmt = stmt.where(PriceBook.customer_id == customer_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/price-books/{price_book_id}", response_model=PriceBookResponse)
async def get_price_book(
    price_book_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> PriceBook:
    book = await session.get(PriceBook, price_book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price book not found",
        )
    return book


@router.post(
    "/price-books",
    response_model=PriceBookResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_price_book(
    payload: PriceBookCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> PriceBook:
    book = PriceBook(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(book)
    await session.flush()
    await session.refresh(book)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_PRICE_BOOK,
        entity_id=book.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return book


@router.patch("/price-books/{price_book_id}", response_model=PriceBookResponse)
async def update_price_book(
    price_book_id: str,
    payload: PriceBookUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> PriceBook:
    book = await session.get(PriceBook, price_book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price book not found",
        )
    changes = payload.model_dump(exclude_unset=True)
    old_value = _audit_old(book, changes)
    for key, value in changes.items():
        setattr(book, key, value)
    book.updated_by = user.subject
    await session.flush()
    await session.refresh(book)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_PRICE_BOOK,
        entity_id=book.id,
        actor=user.subject,
        old_value=old_value,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return book


@router.delete(
    "/price-books/{price_book_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_price_book(
    price_book_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> None:
    book = await session.get(PriceBook, price_book_id)
    if book is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price book not found",
        )
    await session.delete(book)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_PRICE_BOOK,
        entity_id=price_book_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Prices
# --------------------------------------------------------------------------- #


@router.get("/prices", response_model=list[PriceResponse])
async def list_prices(
    sku_id: str | None = Query(None),
    price_book_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> list[Price]:
    stmt = select(Price)
    if sku_id is not None:
        stmt = stmt.where(Price.sku_id == sku_id)
    if price_book_id is not None:
        stmt = stmt.where(Price.price_book_id == price_book_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/prices/{price_id}", response_model=PriceResponse)
async def get_price(
    price_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.PRICING_READ)),
) -> Price:
    price = await session.get(Price, price_id)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price not found"
        )
    return price


async def _validate_price_refs(
    session: AsyncSession, sku_id: str, price_book_id: str
) -> None:
    if await session.get(Sku, sku_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SKU not found"
        )
    if await session.get(PriceBook, price_book_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Price book not found",
        )


@router.post(
    "/prices", response_model=PriceResponse, status_code=status.HTTP_201_CREATED
)
async def create_price(
    payload: PriceCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> Price:
    await _validate_price_refs(session, payload.sku_id, payload.price_book_id)
    price = Price(
        **payload.model_dump(),
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(price)
    await session.flush()
    await session.refresh(price)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_PRICE,
        entity_id=price.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return price


@router.patch("/prices/{price_id}", response_model=PriceResponse)
async def update_price(
    price_id: str,
    payload: PriceUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> Price:
    price = await session.get(Price, price_id)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price not found"
        )
    changes = payload.model_dump(exclude_unset=True)
    await _validate_price_refs(
        session,
        changes.get("sku_id", price.sku_id),
        changes.get("price_book_id", price.price_book_id),
    )
    old_value = _audit_old(price, changes)
    for key, value in changes.items():
        setattr(price, key, value)
    price.updated_by = user.subject
    await session.flush()
    await session.refresh(price)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_PRICE,
        entity_id=price.id,
        actor=user.subject,
        old_value=old_value,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return price


@router.delete("/prices/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(
    price_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.PRICING_WRITE)),
) -> None:
    price = await session.get(Price, price_id)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Price not found"
        )
    await session.delete(price)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_PRICE,
        entity_id=price_id,
        actor=user.subject,
    )
