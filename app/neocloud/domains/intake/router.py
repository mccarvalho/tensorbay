"""Order Form intake endpoints.

Public (no login; the long random link token is the credential):
  GET  /public/intake/{token}   what the page shows (no prices)
  POST /public/intake/{token}   the customer submits the data

Staff (CUSTOMER_WRITE / CUSTOMER_READ):
  POST /intake/opportunity/{id}/link     create a link (revokes one still waiting)
  GET  /intake/opportunity/{id}          links and submitted data for the deal
  POST /intake/{intake_id}/reopen        let the customer edit again
  POST /intake/{intake_id}/revoke        kill the link
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import Settings, get_settings
from neocloud.db.session import get_session
from neocloud.domains.customers.models import Customer
from neocloud.domains.intake import service
from neocloud.domains.intake.models import IntakeStatus, OrderFormIntake
from neocloud.domains.intake.schemas import IntakeAdmin, IntakeFormInfo, IntakeSubmission
from neocloud.domains.sales.models import Opportunity

router = APIRouter(prefix="/intake", tags=["Order Form intake"])
public_router = APIRouter(prefix="/public/intake", tags=["Order Form intake (public)"])

Session = Annotated[AsyncSession, Depends(get_session)]
Cfg = Annotated[Settings, Depends(get_settings)]
Writer = Annotated[CurrentUser, Depends(require_permission(Permission.CUSTOMER_WRITE))]
Reader = Annotated[CurrentUser, Depends(require_permission(Permission.CUSTOMER_READ))]


# --------------------------------------------------------------------------- #
# Public
# --------------------------------------------------------------------------- #
async def _usable(session: AsyncSession, token: str) -> OrderFormIntake:
    intake = await service.by_token(session, token)
    if intake is None or intake.status == IntakeStatus.REVOKED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link is not valid.")
    if service.is_expired(intake):
        raise HTTPException(status.HTTP_410_GONE, "This link has expired. Please ask your TensorBay contact for a new one.")
    return intake


@public_router.get("/{token}", response_model=IntakeFormInfo)
async def public_form(token: str, session: Session) -> IntakeFormInfo:
    intake = await _usable(session, token)
    opp = await session.get(Opportunity, intake.opportunity_id)
    customer = await session.get(Customer, opp.customer_id) if opp else None
    if opp is None or customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link is not valid.")
    pending = intake.status == IntakeStatus.PENDING
    return IntakeFormInfo(
        status=intake.status, customer_name=customer.legal_name, gpu_model=opp.gpu_model, quantity=opp.quantity,
        contact_name=opp.account_owner, expires_at=intake.expires_at, submitted_at=intake.submitted_at,
        # A reopened link starts from what was sent before. A submitted one shows nothing.
        prefill=(intake.data if pending else None) or ({"legal_name": customer.legal_name} if pending else None),
    )


@public_router.post("/{token}", response_model=IntakeFormInfo)
async def public_submit(
    token: str, payload: IntakeSubmission, session: Session, settings: Cfg, background: BackgroundTasks
) -> IntakeFormInfo:
    intake = await _usable(session, token)
    if intake.status == IntakeStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This form was already submitted. Contact your TensorBay representative to change it.")
    opp = await session.get(Opportunity, intake.opportunity_id)
    customer = await session.get(Customer, opp.customer_id) if opp else None
    if opp is None or customer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link is not valid.")

    intake.data = payload.model_dump(mode="json")
    intake.status = IntakeStatus.SUBMITTED
    intake.submitted_at = datetime.now(UTC)
    intake.updated_by = f"customer:{payload.signatory_email}"
    await record_audit(
        session, action="submit", entity_type="OrderFormIntake", entity_id=intake.id,
        actor=f"customer:{payload.signatory_email}", new_value={"opportunity_id": opp.id},
    )
    notice = service.SubmittedNotice(
        opportunity_id=opp.id, opportunity_label=opp.short_name or f"{opp.gpu_model} x {opp.quantity}",
        customer_name=payload.legal_name, signatory=f"{payload.signatory_name}, {payload.signatory_title}",
        signatory_email=str(payload.signatory_email), gpu_model=opp.gpu_model, quantity=opp.quantity,
    )
    # After the response (and the commit): the owner is told the MSA can be generated.
    background.add_task(service.send_submitted_email, settings, notice, service.recipients_for(settings, opp.account_owner_email))
    return IntakeFormInfo(
        status=intake.status, customer_name=customer.legal_name, gpu_model=opp.gpu_model, quantity=opp.quantity,
        contact_name=opp.account_owner, expires_at=intake.expires_at, submitted_at=intake.submitted_at,
    )


# --------------------------------------------------------------------------- #
# Staff
# --------------------------------------------------------------------------- #
def _admin(settings: Settings, intake: OrderFormIntake, with_data: bool = True) -> IntakeAdmin:
    return IntakeAdmin(
        id=intake.id, opportunity_id=intake.opportunity_id, status=intake.status,
        expired=service.is_expired(intake) and intake.status == IntakeStatus.PENDING,
        expires_at=intake.expires_at, submitted_at=intake.submitted_at, created_at=intake.created_at,
        data=intake.data if with_data else None,
        token=service.reveal_token(settings, intake) if intake.status == IntakeStatus.PENDING else None,
    )


@router.post("/opportunity/{opportunity_id}/link", response_model=IntakeAdmin, status_code=status.HTTP_201_CREATED)
async def create_link(opportunity_id: str, session: Session, settings: Cfg, user: Writer) -> IntakeAdmin:
    if await session.get(Opportunity, opportunity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    intake, token = await service.create_link(session, settings, opportunity_id, user.subject)
    await record_audit(session, action="create_link", entity_type="OrderFormIntake", entity_id=intake.id, actor=user.subject,
                       new_value={"opportunity_id": opportunity_id})
    await session.refresh(intake)
    out = _admin(settings, intake)
    out.token = token  # always shown right after creating, even without a stored copy
    return out


@router.get("/opportunity/{opportunity_id}", response_model=list[IntakeAdmin])
async def list_for_opportunity(opportunity_id: str, session: Session, settings: Cfg, _user: Reader) -> list[IntakeAdmin]:
    rows = (
        await session.execute(
            select(OrderFormIntake).where(OrderFormIntake.opportunity_id == opportunity_id)
            .order_by(OrderFormIntake.created_at.desc())
        )
    ).scalars().all()
    return [_admin(settings, r) for r in rows if r.status != IntakeStatus.REVOKED]


async def _get(session: AsyncSession, intake_id: str) -> OrderFormIntake:
    intake = await session.get(OrderFormIntake, intake_id)
    if intake is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link not found")
    return intake


@router.post("/{intake_id}/reopen", response_model=IntakeAdmin)
async def reopen(intake_id: str, session: Session, settings: Cfg, user: Writer) -> IntakeAdmin:
    """Back to PENDING with a fresh expiry; the customer sees what they sent before and can fix it."""
    intake = await _get(session, intake_id)
    if intake.status == IntakeStatus.REVOKED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This link was revoked. Create a new one.")
    intake.status, intake.expires_at, intake.updated_by = IntakeStatus.PENDING, datetime.now(UTC) + timedelta(days=service.LINK_DAYS), user.subject
    await record_audit(session, action="reopen", entity_type="OrderFormIntake", entity_id=intake.id, actor=user.subject)
    await session.flush()
    await session.refresh(intake)
    return _admin(settings, intake)


@router.post("/{intake_id}/revoke", response_model=IntakeAdmin)
async def revoke(intake_id: str, session: Session, settings: Cfg, user: Writer) -> IntakeAdmin:
    intake = await _get(session, intake_id)
    intake.status, intake.updated_by = IntakeStatus.REVOKED, user.subject
    await record_audit(session, action="revoke", entity_type="OrderFormIntake", entity_id=intake.id, actor=user.subject)
    await session.flush()
    await session.refresh(intake)
    return _admin(settings, intake)
