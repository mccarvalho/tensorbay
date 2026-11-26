"""Availability list: what sales can offer now and in the coming months, by GPU model and site."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.capacity.models import AvailabilityOffer

router = APIRouter(prefix="/capacity/availability", tags=["Capacity"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.CAPACITY_READ))]
WriteUser = Annotated[CurrentUser, Depends(require_permission(Permission.INVENTORY_WRITE))]
Session = Annotated[AsyncSession, Depends(get_session)]
ENTITY = "capacity.availability"


class OfferBase(BaseModel):
    gpu_model: str = Field(..., min_length=1, max_length=64)
    cooling: Literal["AIR", "LIQUID"] | None = None
    quantity_unit: Literal["GPUS", "RACKS"] = "GPUS"
    site: str = Field(..., min_length=1, max_length=255)
    available_from: date | None = None  # null = immediate; stored as the 1st of the month
    total_qty: int | None = Field(default=None, ge=0)
    available_qty: int = Field(..., ge=0)
    price_per_gpu_hour: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    notes: str | None = None

    @field_validator("available_from")
    @classmethod
    def _first_of_month(cls, v: date | None) -> date | None:
        return v.replace(day=1) if v else v


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    gpu_model: str | None = Field(default=None, min_length=1, max_length=64)
    cooling: Literal["AIR", "LIQUID"] | None = None
    quantity_unit: Literal["GPUS", "RACKS"] | None = None
    site: str | None = Field(default=None, min_length=1, max_length=255)
    available_from: date | None = None
    total_qty: int | None = Field(default=None, ge=0)
    available_qty: int | None = Field(default=None, ge=0)
    price_per_gpu_hour: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=4)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = None

    @field_validator("available_from")
    @classmethod
    def _first_of_month(cls, v: date | None) -> date | None:
        return v.replace(day=1) if v else v


class OfferRead(OfferBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class OfferText(BaseModel):
    text: str


def _check(total: int | None, available: int | None) -> None:
    if total is not None and available is not None and available > total:
        raise HTTPException(status_code=422, detail="Available quantity cannot exceed the total")


def _label(o: AvailabilityOffer) -> str:
    cooling = {"AIR": " - Air Cooling", "LIQUID": " - Liquid Cooling"}.get(o.cooling or "", "")
    return f"{o.gpu_model}{cooling}"


def _qty(n: int, unit: str) -> str:
    return f"{n:,} racks" if unit == "RACKS" else f"{n:,} GPUs"


def _price(o: AvailabilityOffer) -> str | None:
    if o.price_per_gpu_hour is None:
        return None
    return f"{o.currency} {Decimal(o.price_per_gpu_hour):.2f} per GPU-hour" if o.currency != "USD" else \
        f"US$ {Decimal(o.price_per_gpu_hour):.2f} per GPU-hour"


def render_text(offers: list[AvailabilityOffer]) -> str:
    """The list in the form sales sends to customers, prices included where they are set."""
    groups: dict[date | None, list[AvailabilityOffer]] = {}
    for o in sorted(offers, key=lambda x: (x.available_from or date.min, x.gpu_model, x.site)):
        groups.setdefault(o.available_from, []).append(o)
    blocks = []
    for month, rows in groups.items():
        head = "Immediate Availability" if month is None else f"{month:%B %Y}"
        lines = [head, ""]
        for o in rows:
            lines.append(_label(o))
            if o.total_qty is not None:
                lines.append(_qty(o.total_qty, o.quantity_unit))
            lines.append(f"Available at the moment: {_qty(o.available_qty, o.quantity_unit)}")
            lines.append(f"Site: {o.site}")
            if (price := _price(o)):
                lines.append(f"Price: {price}")
            lines.append("")
        blocks.append("\n".join(lines).rstrip())
    return "\n\n".join(blocks)


async def _get(session: AsyncSession, offer_id: str) -> AvailabilityOffer:
    o = await session.get(AvailabilityOffer, offer_id)
    if o is None:
        raise HTTPException(status_code=404, detail="Availability entry not found")
    return o


async def _all(session: AsyncSession) -> list[AvailabilityOffer]:
    rows = await session.execute(
        select(AvailabilityOffer).order_by(
            AvailabilityOffer.available_from.is_(None).desc(), AvailabilityOffer.available_from,
            AvailabilityOffer.gpu_model, AvailabilityOffer.site,
        )
    )
    return list(rows.scalars().all())


@router.get("", response_model=list[OfferRead])
async def list_offers(session: Session, _user: ReadUser):
    return await _all(session)


@router.get("/text", response_model=OfferText)
async def offers_text(session: Session, _user: ReadUser):
    return OfferText(text=render_text(await _all(session)))


@router.post("", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
async def create_offer(payload: OfferCreate, session: Session, user: WriteUser):
    _check(payload.total_qty, payload.available_qty)
    o = AvailabilityOffer(**payload.model_dump(), created_by=user.subject, updated_by=user.subject)
    o.currency = o.currency.upper()
    session.add(o)
    await session.flush()
    await record_audit(session, action="create", entity_type=ENTITY, entity_id=o.id, actor=user.subject,
                       new_value=payload.model_dump(mode="json"))
    await session.refresh(o)
    return o


@router.patch("/{offer_id}", response_model=OfferRead)
async def update_offer(offer_id: str, payload: OfferUpdate, session: Session, user: WriteUser):
    o = await _get(session, offer_id)
    changes = payload.model_dump(exclude_unset=True)
    for key in ("gpu_model", "site", "available_qty", "quantity_unit", "currency"):
        if key in changes and changes[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be empty")
    for k, v in changes.items():
        setattr(o, k, v.upper() if k == "currency" and v else v)
    _check(o.total_qty, o.available_qty)
    o.updated_by = user.subject
    await session.flush()
    await record_audit(session, action="update", entity_type=ENTITY, entity_id=o.id, actor=user.subject,
                       new_value=payload.model_dump(mode="json", exclude_unset=True))
    await session.refresh(o)
    return o


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_offer(offer_id: str, session: Session, user: WriteUser) -> None:
    o = await _get(session, offer_id)
    await session.delete(o)
    await record_audit(session, action="delete", entity_type=ENTITY, entity_id=offer_id, actor=user.subject)
