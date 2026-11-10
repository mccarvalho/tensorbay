"""Leads API.

* ``POST /v1/leads/ingest`` is PUBLIC but protected by a shared bearer token. The
  website form backend calls it server-side. It is idempotent on
  ``submission_id`` so retries are safe.
* Everything else is a normal Cognito-authenticated API gated on
  ``lead.read`` / ``lead.write``. Account Managers (SALES) only see leads
  assigned to them; managers/executives/super-admins see all.
"""

from __future__ import annotations

import hmac
import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import Settings, get_settings
from neocloud.core.logging import get_logger
from neocloud.db.session import get_session
from neocloud.domains.customers.models import (
    Activity,
    ActivityType,
    Contact,
    ContactType,
    Customer,
    CustomerStatus,
)
from neocloud.domains.economics.models import SalesRep
from neocloud.domains.leads import service as lead_service
from neocloud.domains.leads.models import OPEN_STATUSES, Lead, LeadStatus
from neocloud.domains.leads.parsing import (
    clean,
    extract_region_from_message,
    parse_gpu_count,
    split_region,
)
from neocloud.domains.leads.schemas import (
    LeadConvert,
    LeadConvertResult,
    LeadDisqualify,
    LeadIngest,
    LeadIngestResult,
    LeadRead,
    LeadUpdate,
)
from neocloud.domains.sales.models import Opportunity, SalesStage

logger = get_logger(__name__)

router = APIRouter(prefix="/leads", tags=["Leads"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.LEAD_READ))]
WriteUser = Annotated[CurrentUser, Depends(require_permission(Permission.LEAD_WRITE))]
Session = Annotated[AsyncSession, Depends(get_session)]

ENTITY_LEAD = "lead"
MAX_RAW_PAYLOAD_BYTES = 20_000
_PRIVILEGED_ROLES = {"SUPER_ADMIN", "EXECUTIVE", "SALES_MANAGER"}


# --------------------------------------------------------------------------- #
# Ingest (public, token protected)
# --------------------------------------------------------------------------- #
async def require_ingest_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = lead_service.resolve_ingest_token(settings)
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lead ingestion is not configured",
        )
    supplied = ""
    if authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _find_by_submission(session: AsyncSession, submission_id: str) -> Lead | None:
    return (
        await session.execute(select(Lead).where(Lead.submission_id == submission_id))
    ).scalars().first()


async def _rep_name(session: AsyncSession, rep_id: str | None) -> str | None:
    if not rep_id:
        return None
    rep = await session.get(SalesRep, rep_id)
    return rep.name if rep else None


@router.post(
    "/ingest",
    response_model=LeadIngestResult,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Duplicate submission_id - nothing new created"},
        401: {"description": "Invalid or missing token"},
        413: {"description": "Payload too large"},
        422: {"description": "Validation error"},
        503: {"description": "Ingestion not configured"},
    },
)
async def ingest_lead(
    payload: LeadIngest,
    response: Response,
    background: BackgroundTasks,
    session: Session,
    settings: Annotated[Settings, Depends(get_settings)],
    _auth: Annotated[None, Depends(require_ingest_token)],
):
    # Idempotency: a retry of the same submission never creates a second lead.
    existing = await _find_by_submission(session, payload.submission_id)
    if existing is not None:
        response.status_code = status.HTTP_200_OK
        return LeadIngestResult(
            id=existing.id,
            status="duplicate",
            assigned_to=await _rep_name(session, existing.assigned_rep_id),
            needs_review=existing.needs_review,
        )

    raw = payload.model_dump(mode="json")
    if len(json.dumps(raw, default=str)) > MAX_RAW_PAYLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Payload too large",
        )

    name = clean(payload.name)
    if name is None:
        raise HTTPException(status_code=422, detail="name is required")
    email = str(payload.email).strip().lower()

    # Region: prefer structured fields; fall back to the legacy embedded line.
    region = clean(payload.region)
    country = clean(payload.country)
    if region and not country:
        region, country = split_region(region)
    message = clean(payload.message)
    msg_region, msg_country, message = extract_region_from_message(message)
    if not region:
        region = msg_region
    country = country or msg_country

    # Same email already has open work -> link it so reps see the repeat.
    prior = (
        await session.execute(
            select(Lead)
            .where(func.lower(Lead.email) == email, Lead.status.in_(OPEN_STATUSES))
            .order_by(Lead.created_at.asc())
            .limit(1)
        )
    ).scalars().first()

    assignee = await lead_service.pick_assignee(session, region, country)

    lead = Lead(
        submission_id=payload.submission_id,
        source=clean(payload.source) or "website_pricing_request",
        name=name,
        email=email,
        company=clean(payload.company),
        sku_of_interest=clean(payload.sku_of_interest),
        gpu_count=parse_gpu_count(payload.gpu_count),
        pricing_model_or_term=clean(payload.pricing_model_or_term),
        site_language=clean(payload.site_language),
        region=region,
        country=country,
        message=message,
        page_url=clean(payload.page_url),
        submitted_at=payload.submitted_at,
        status=LeadStatus.NEW,
        assigned_rep_id=assignee.id if assignee else None,
        needs_review=region is None,
        duplicate_of_id=prior.id if prior else None,
        raw_payload=raw,
        created_by="website",
        updated_by="website",
    )
    session.add(lead)
    try:
        await session.flush()
    except IntegrityError:
        # Lost a race with a concurrent retry of the same submission_id.
        await session.rollback()
        existing = await _find_by_submission(session, payload.submission_id)
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return LeadIngestResult(
            id=existing.id,
            status="duplicate",
            assigned_to=await _rep_name(session, existing.assigned_rep_id),
            needs_review=existing.needs_review,
        )

    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_LEAD,
        entity_id=lead.id,
        actor="website",
        new_value={
            "submission_id": lead.submission_id,
            "region": lead.region,
            "assigned_rep_id": lead.assigned_rep_id,
        },
        source="webhook",
    )

    notice = lead_service.LeadNotice(
        lead_id=lead.id,
        name=lead.name,
        email=lead.email,
        company=lead.company,
        sku_of_interest=lead.sku_of_interest,
        gpu_count=lead.gpu_count,
        pricing_model_or_term=lead.pricing_model_or_term,
        region=lead.region,
        country=lead.country,
        message=lead.message,
        assignee_name=assignee.name if assignee else None,
        is_repeat=prior is not None,
        needs_review=lead.needs_review,
    )
    recipients = lead_service.lead_recipients(settings, assignee.email if assignee else None)
    background.add_task(lead_service.send_new_lead_email, settings, notice, recipients)

    return LeadIngestResult(
        id=lead.id,
        status="created",
        assigned_to=assignee.name if assignee else None,
        needs_review=lead.needs_review,
    )


# --------------------------------------------------------------------------- #
# Authenticated API
# --------------------------------------------------------------------------- #
def _is_privileged(user: CurrentUser) -> bool:
    return bool(_PRIVILEGED_ROLES.intersection(set(user.roles or [])))


async def _rep_ids_for_user(session: AsyncSession, user: CurrentUser) -> list[str]:
    result = await session.execute(
        select(SalesRep.id).where(SalesRep.cognito_sub == user.subject)
    )
    return list(result.scalars().all())


async def _get_lead_or_404(session: AsyncSession, lead_id: str) -> Lead:
    lead = await session.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    return lead


async def _get_visible_lead(session: AsyncSession, lead_id: str, user: CurrentUser) -> Lead:
    lead = await _get_lead_or_404(session, lead_id)
    if not _is_privileged(user):
        if lead.assigned_rep_id not in await _rep_ids_for_user(session, user):
            raise HTTPException(status_code=403, detail="Not your lead")
    return lead


@router.get("", response_model=list[LeadRead])
async def list_leads(
    session: Session,
    user: ReadUser,
    status_filter: LeadStatus | None = Query(default=None, alias="status"),
    assigned_rep_id: str | None = None,
    needs_review: bool | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Lead).order_by(Lead.created_at.desc())
    if status_filter:
        stmt = stmt.where(Lead.status == status_filter)
    if assigned_rep_id:
        stmt = stmt.where(Lead.assigned_rep_id == assigned_rep_id)
    if needs_review is not None:
        stmt = stmt.where(Lead.needs_review.is_(needs_review))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Lead.name.ilike(like), Lead.email.ilike(like), Lead.company.ilike(like))
        )
    if not _is_privileged(user):
        rep_ids = await _rep_ids_for_user(session, user)
        if not rep_ids:
            return []
        stmt = stmt.where(Lead.assigned_rep_id.in_(rep_ids))
    return (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(lead_id: str, session: Session, user: ReadUser):
    return await _get_visible_lead(session, lead_id, user)


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(lead_id: str, payload: LeadUpdate, session: Session, user: WriteUser):
    lead = await _get_visible_lead(session, lead_id, user)
    if lead.status == LeadStatus.CONVERTED:
        raise HTTPException(status_code=409, detail="Converted leads can't be edited")
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.get("status")
    if new_status == LeadStatus.CONVERTED:
        raise HTTPException(status_code=422, detail="Use /convert to convert a lead")
    if new_status == LeadStatus.DISQUALIFIED:
        raise HTTPException(status_code=422, detail="Use /disqualify to disqualify a lead")
    if "assigned_rep_id" in changes and changes["assigned_rep_id"] is not None:
        # Only managers can reassign; an AM can't hand leads around freely.
        if not _is_privileged(user):
            raise HTTPException(status_code=403, detail="Only managers can reassign leads")
        if await session.get(SalesRep, changes["assigned_rep_id"]) is None:
            raise HTTPException(status_code=404, detail="Assigned rep not found")
    for key, value in changes.items():
        setattr(lead, key, value)
    lead.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_LEAD,
        entity_id=lead.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(lead)
    return lead


@router.post("/{lead_id}/disqualify", response_model=LeadRead)
async def disqualify_lead(
    lead_id: str, payload: LeadDisqualify, session: Session, user: WriteUser
):
    lead = await _get_visible_lead(session, lead_id, user)
    if lead.status == LeadStatus.CONVERTED:
        raise HTTPException(status_code=409, detail="Lead already converted")
    lead.status = LeadStatus.DISQUALIFIED
    lead.disqualified_reason = payload.reason
    lead.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="disqualify",
        entity_type=ENTITY_LEAD,
        entity_id=lead.id,
        actor=user.subject,
        new_value={"reason": payload.reason},
    )
    await session.refresh(lead)
    return lead


@router.post("/{lead_id}/convert", response_model=LeadConvertResult)
async def convert_lead(
    lead_id: str, payload: LeadConvert, session: Session, user: WriteUser
):
    """Turn a lead into a PROSPECT customer + contact + activity (+ opportunity)."""
    lead = await _get_visible_lead(session, lead_id, user)
    if lead.status == LeadStatus.CONVERTED:
        raise HTTPException(status_code=409, detail="Lead already converted")

    gpu_model = payload.gpu_model or lead.sku_of_interest
    quantity = payload.quantity or lead.gpu_count
    if payload.create_opportunity:
        missing = [
            n
            for n, v in (
                ("gpu_model", gpu_model),
                ("quantity", quantity),
                ("duration_months", payload.duration_months),
                ("commercial_model", payload.commercial_model),
                ("expected_mrr", payload.expected_mrr),
            )
            if v in (None, "")
        ]
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"To create an opportunity please provide: {', '.join(missing)}",
            )

    rep = await session.get(SalesRep, lead.assigned_rep_id) if lead.assigned_rep_id else None
    legal_name = (payload.customer_name or lead.company or lead.name).strip()

    # Reuse an existing customer of the same name instead of duplicating it.
    customer = (
        await session.execute(
            select(Customer).where(func.lower(Customer.legal_name) == legal_name.lower())
        )
    ).scalars().first()
    customer_created = customer is None
    if customer is None:
        customer = Customer(
            legal_name=legal_name,
            status=CustomerStatus.PROSPECT,
            account_owner=rep.name if rep else None,
            created_by=user.subject,
            updated_by=user.subject,
        )
        session.add(customer)
        await session.flush()

    contact = (
        await session.execute(
            select(Contact).where(
                Contact.customer_id == customer.id,
                func.lower(Contact.email) == lead.email.lower(),
            )
        )
    ).scalars().first()
    if contact is None:
        contact = Contact(
            customer_id=customer.id,
            type=ContactType.COMMERCIAL,
            name=lead.name,
            email=lead.email,
            created_by=user.subject,
            updated_by=user.subject,
        )
        session.add(contact)
        await session.flush()

    details = [
        f"Source: {lead.source}",
        f"Region: {' · '.join(p for p in (lead.region, lead.country) if p) or '-'}",
        f"SKU of interest: {lead.sku_of_interest or '-'}",
        f"GPU count: {lead.gpu_count if lead.gpu_count is not None else '-'}",
        f"Pricing model / term: {lead.pricing_model_or_term or '-'}",
    ]
    notes = "\n".join(details) + (f"\n\n{lead.message}" if lead.message else "")
    session.add(
        Activity(
            customer_id=customer.id,
            contact_id=contact.id,
            type=ActivityType.EMAIL,
            subject="Website pricing request",
            notes=notes,
            occurred_at=lead.submitted_at or datetime.now(timezone.utc),
            created_by=user.subject,
            updated_by=user.subject,
        )
    )

    opportunity_id: str | None = None
    if payload.create_opportunity:
        opp = Opportunity(
            customer_id=customer.id,
            gpu_model=str(gpu_model),
            quantity=int(quantity),  # type: ignore[arg-type]
            duration_months=int(payload.duration_months),  # type: ignore[arg-type]
            commercial_model=str(payload.commercial_model),
            expected_mrr=payload.expected_mrr,
            probability=10,
            sales_stage=SalesStage.PROSPECTING,
            account_owner=rep.name if rep else None,
            account_owner_email=rep.email if rep else None,
            account_owner_sub=rep.cognito_sub if rep else None,
            created_by=user.subject,
            updated_by=user.subject,
        )
        session.add(opp)
        await session.flush()
        opportunity_id = opp.id

    lead.status = LeadStatus.CONVERTED
    lead.converted_customer_id = customer.id
    lead.converted_opportunity_id = opportunity_id
    lead.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="convert",
        entity_type=ENTITY_LEAD,
        entity_id=lead.id,
        actor=user.subject,
        new_value={
            "customer_id": customer.id,
            "opportunity_id": opportunity_id,
            "customer_created": customer_created,
        },
    )
    await session.refresh(lead)
    return LeadConvertResult(
        lead=LeadRead.model_validate(lead),
        customer_id=customer.id,
        contact_id=contact.id,
        opportunity_id=opportunity_id,
        customer_created=customer_created,
    )
