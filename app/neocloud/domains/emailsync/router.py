"""Email sync API: mailboxes (admin) and the unmatched-email triage queue."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.core.config import Settings, get_settings
from neocloud.db.session import get_session
from neocloud.domains.customers.models import Activity, ActivityType, Contact, Customer
from neocloud.domains.emailsync import service
from neocloud.domains.emailsync.gmail import GmailReader, load_service_account
from neocloud.domains.emailsync.models import Mailbox, UnmatchedEmail, UnmatchedStatus
from neocloud.domains.emailsync.schemas import (
    MailboxCreate,
    MailboxRead,
    MailboxUpdate,
    SyncRunResult,
    SyncStatus,
    UnmatchedAssign,
    UnmatchedRead,
)

router = APIRouter(prefix="/email-sync", tags=["Email sync"])

Session = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[CurrentUser, Depends(require_permission(Permission.USER_ADMIN))]
Reader = Annotated[CurrentUser, Depends(require_permission(Permission.CUSTOMER_READ))]
Writer = Annotated[CurrentUser, Depends(require_permission(Permission.CUSTOMER_WRITE))]


# --------------------------------------------------------------------------- #
# Mailboxes (admin)
# --------------------------------------------------------------------------- #
@router.get("/status", response_model=SyncStatus)
async def sync_status(
    session: Session, _user: Reader, settings: Annotated[Settings, Depends(get_settings)]
):
    info = load_service_account(settings)
    boxes = (await session.execute(select(Mailbox).order_by(Mailbox.address))).scalars().all()
    pending = (
        await session.execute(
            select(func.count(UnmatchedEmail.id)).where(
                UnmatchedEmail.status == UnmatchedStatus.PENDING
            )
        )
    ).scalar_one()
    return SyncStatus(
        configured=info is not None,
        service_account=info.get("client_email") if info else None,
        mailboxes=list(boxes),
        pending_unmatched=pending,
    )


@router.post("/mailboxes", response_model=MailboxRead, status_code=status.HTTP_201_CREATED)
async def add_mailbox(payload: MailboxCreate, session: Session, user: Admin):
    address = str(payload.address).strip().lower()
    if (await session.execute(select(Mailbox.id).where(Mailbox.address == address))).first():
        raise HTTPException(status_code=409, detail="Mailbox already added")
    mb = Mailbox(
        address=address,
        capture_unmatched=payload.capture_unmatched,
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(mb)
    await session.flush()
    await record_audit(
        session, action="create", entity_type="mailbox", entity_id=mb.id,
        actor=user.subject, new_value={"address": address},
    )
    await session.refresh(mb)
    return mb


@router.patch("/mailboxes/{mailbox_id}", response_model=MailboxRead)
async def update_mailbox(mailbox_id: str, payload: MailboxUpdate, session: Session, user: Admin):
    mb = await session.get(Mailbox, mailbox_id)
    if mb is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(mb, k, v)
    mb.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="update", entity_type="mailbox", entity_id=mb.id,
        actor=user.subject, new_value=changes,
    )
    await session.refresh(mb)
    return mb


@router.delete("/mailboxes/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_mailbox(mailbox_id: str, session: Session, user: Admin) -> None:
    mb = await session.get(Mailbox, mailbox_id)
    if mb is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    await session.delete(mb)
    await record_audit(
        session, action="delete", entity_type="mailbox", entity_id=mailbox_id, actor=user.subject
    )


@router.post("/mailboxes/{mailbox_id}/sync", response_model=SyncRunResult)
async def sync_now(
    mailbox_id: str,
    session: Session,
    _user: Admin,
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Run a sync for one mailbox right now (also a connectivity test)."""
    mb = await session.get(Mailbox, mailbox_id)
    if mb is None:
        raise HTTPException(status_code=404, detail="Mailbox not found")
    info = load_service_account(settings)
    if info is None:
        raise HTTPException(status_code=409, detail="Gmail service account is not configured")
    res = await service.sync_mailbox(session, GmailReader(info, mb.address), mb, settings)
    return SyncRunResult(
        mailbox=mb.address, logged=res.logged, unmatched=res.unmatched,
        skipped=res.skipped, error=mb.last_error,
    )


# --------------------------------------------------------------------------- #
# Unmatched inbox
# --------------------------------------------------------------------------- #
@router.get("/unmatched", response_model=list[UnmatchedRead])
async def list_unmatched(
    session: Session,
    _user: Reader,
    status_filter: UnmatchedStatus = Query(default=UnmatchedStatus.PENDING, alias="status"),
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    stmt = (
        select(UnmatchedEmail)
        .where(UnmatchedEmail.status == status_filter)
        .order_by(UnmatchedEmail.sent_at.desc())
        .limit(limit)
    )
    return (await session.execute(stmt)).scalars().all()


async def _get_pending(session: AsyncSession, item_id: str) -> UnmatchedEmail:
    item = await session.get(UnmatchedEmail, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Email not found")
    if item.status != UnmatchedStatus.PENDING:
        raise HTTPException(status_code=409, detail=f"Email already {item.status.lower()}")
    return item


@router.post("/unmatched/{item_id}/assign", response_model=UnmatchedRead)
async def assign_unmatched(item_id: str, payload: UnmatchedAssign, session: Session, user: Writer):
    item = await _get_pending(session, item_id)
    customer = await session.get(Customer, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")

    externals = [a for a in item.external_addrs.split(",") if a]
    wanted = (str(payload.contact_email).lower() if payload.contact_email else None) or (
        externals[0] if externals else None
    )
    contact: Contact | None = None
    if wanted:
        contact = (
            await session.execute(
                select(Contact).where(
                    Contact.customer_id == customer.id, func.lower(Contact.email) == wanted
                )
            )
        ).scalars().first()
        if contact is None and payload.create_contact:
            contact = Contact(
                customer_id=customer.id,
                type=payload.contact_type,
                name=(payload.contact_name or wanted.split("@")[0]).strip(),
                role=(payload.contact_role or None),
                email=wanted,
                created_by=user.subject,
                updated_by=user.subject,
            )
            session.add(contact)
            await session.flush()

    dup = (
        await session.execute(
            select(Activity.id).where(
                Activity.customer_id == customer.id, Activity.external_id == item.message_id
            )
        )
    ).first()
    if dup is None:
        session.add(
            Activity(
                customer_id=customer.id,
                contact_id=contact.id if contact else None,
                type=ActivityType.EMAIL,
                subject=item.subject,
                notes=item.body_text,
                occurred_at=item.sent_at,
                source=service.SOURCE,
                direction=item.direction,
                external_id=item.message_id,
                created_by=user.subject,
                updated_by=user.subject,
            )
        )
    item.status = UnmatchedStatus.ASSIGNED
    item.resolved_customer_id = customer.id
    item.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="assign", entity_type="unmatched_email", entity_id=item.id,
        actor=user.subject, new_value={"customer_id": customer.id},
    )
    await session.refresh(item)
    return item


@router.post("/unmatched/{item_id}/dismiss", response_model=UnmatchedRead)
async def dismiss_unmatched(item_id: str, session: Session, user: Writer):
    item = await _get_pending(session, item_id)
    item.status = UnmatchedStatus.DISMISSED
    item.body_text = None  # not a customer email: don't keep the content around
    item.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="dismiss", entity_type="unmatched_email", entity_id=item.id,
        actor=user.subject,
    )
    await session.refresh(item)
    return item
