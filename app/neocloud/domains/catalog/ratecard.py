"""The rate card: list price per GPU-hour by platform, term and upfront share."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.catalog.models import RateCard

router = APIRouter(prefix="/pricing/rate-card", tags=["Pricing"])
ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.PRICING_READ))]
AdminUser = Annotated[CurrentUser, Depends(require_permission(Permission.USER_ADMIN))]
Session = Annotated[AsyncSession, Depends(get_session)]


def platform_key(gpu_model: str | None) -> str | None:
    """The rate card platform of a CRM GPU model name ("HGX B300 liquid-cooled" -> "B300")."""
    m = (gpu_model or "").upper().replace(" ", "").replace("-", "").replace("_", "")
    for key, tokens in (("GB300", ("GB300",)), ("VR200", ("VR200", "VERARUBIN")), ("B300", ("B300",)), ("B200", ("B200",))):
        if any(t in m for t in tokens):
            return key
    return None  # GB200, A100, H200...: no list price


class RateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    platform: str
    term_months: int
    upfront_pct: Decimal
    price_per_gpu_hour: Decimal
    updated_at: datetime


class RateUpdate(BaseModel):
    price_per_gpu_hour: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)


async def rates_for(session: AsyncSession, gpu_model: str | None) -> list[RateCard]:
    key = platform_key(gpu_model)
    if key is None:
        return []
    rows = await session.execute(
        select(RateCard).where(RateCard.platform == key).order_by(RateCard.term_months.desc(), RateCard.upfront_pct)
    )
    return list(rows.scalars().all())


@router.get("", response_model=list[RateRead])
async def list_rates(session: Session, _user: ReadUser):
    rows = await session.execute(select(RateCard).order_by(RateCard.platform, RateCard.term_months.desc(), RateCard.upfront_pct))
    return list(rows.scalars().all())


@router.patch("/{rate_id}", response_model=RateRead)
async def update_rate(rate_id: str, payload: RateUpdate, session: Session, user: AdminUser):
    row = await session.get(RateCard, rate_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Rate not found")
    old = row.price_per_gpu_hour
    row.price_per_gpu_hour, row.updated_by = payload.price_per_gpu_hour, user.subject
    await session.flush()
    await record_audit(session, action="update", entity_type="pricing.rate_card", entity_id=row.id, actor=user.subject,
                       old_value={"price_per_gpu_hour": str(old)}, new_value={"price_per_gpu_hour": str(row.price_per_gpu_hour)})
    await session.refresh(row)
    return row
