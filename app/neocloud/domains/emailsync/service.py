"""Match emails to customers and write them to the activity timeline."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.domains.customers.models import Activity, ActivityType, Contact
from neocloud.domains.emailsync.gmail import (
    GmailReader,
    HistoryExpired,
    MailReader,
    load_service_account,
)
from neocloud.domains.emailsync.models import Mailbox, UnmatchedEmail, UnmatchedStatus
from neocloud.domains.emailsync.parsing import (
    ParsedEmail,
    is_internal,
    parse_gmail_message,
)

logger = get_logger(__name__)

SOURCE = "gmail"
LOOKBACK_DAYS = 7
MAX_PER_RUN = 300


def internal_domains(settings: Settings) -> set[str]:
    return {d.strip().lower() for d in settings.internal_email_domains.split(",") if d.strip()}


@dataclass
class ProcessResult:
    logged: int = 0
    unmatched: int = 0
    skipped: int = 0


def _direction(email: ParsedEmail, internal: set[str]) -> str:
    return "OUT" if is_internal(email.from_addr, internal) else "IN"


def external_addresses(email: ParsedEmail, internal: set[str], mailbox: str) -> list[str]:
    return [
        a for a in email.participants if not is_internal(a, internal) and a != mailbox.lower()
    ]


async def process_email(
    session: AsyncSession, email: ParsedEmail, mailbox: Mailbox, internal: set[str]
) -> ProcessResult:
    """Log ``email`` against every customer that has a matching contact."""
    result = ProcessResult()
    externals = external_addresses(email, internal, mailbox.address)
    contacts: list[Contact] = []
    if externals:
        contacts = list(
            (
                await session.execute(
                    select(Contact).where(func.lower(Contact.email).in_(externals))
                )
            )
            .scalars()
            .all()
        )

    if not contacts:
        if mailbox.capture_unmatched and externals:
            exists = (
                await session.execute(
                    select(UnmatchedEmail.id).where(UnmatchedEmail.message_id == email.message_id)
                )
            ).first()
            if exists is None:
                session.add(
                    UnmatchedEmail(
                        mailbox=mailbox.address,
                        message_id=email.message_id,
                        direction=_direction(email, internal),
                        from_addr=email.from_addr,
                        external_addrs=",".join(externals),
                        subject=email.subject,
                        body_text=email.body_text,
                        sent_at=email.sent_at,
                        status=UnmatchedStatus.PENDING,
                        created_by=f"gmail:{mailbox.address}",
                        updated_by=f"gmail:{mailbox.address}",
                    )
                )
                result.unmatched += 1
        else:
            result.skipped += 1
        return result

    by_customer: dict[str, Contact] = {}
    for c in contacts:
        by_customer.setdefault(c.customer_id, c)

    for customer_id, contact in by_customer.items():
        exists = (
            await session.execute(
                select(Activity.id).where(
                    Activity.customer_id == customer_id,
                    Activity.external_id == email.message_id,
                )
            )
        ).first()
        if exists is not None:
            continue
        session.add(
            Activity(
                customer_id=customer_id,
                contact_id=contact.id,
                type=ActivityType.EMAIL,
                subject=email.subject,
                notes=email.body_text or None,
                occurred_at=email.sent_at,
                source=SOURCE,
                direction=_direction(email, internal),
                external_id=email.message_id,
                created_by=f"gmail:{mailbox.address}",
                updated_by=f"gmail:{mailbox.address}",
            )
        )
        result.logged += 1
    return result


async def sync_mailbox(
    session: AsyncSession, reader: MailReader, mailbox: Mailbox, settings: Settings
) -> ProcessResult:
    """Pull new mail for one mailbox and log it. Updates the mailbox cursor/status."""
    total = ProcessResult()
    internal = internal_domains(settings)
    now = datetime.now(timezone.utc)
    try:
        # Read the cursor first, so mail arriving mid-run is picked up next time.
        new_cursor = await reader.current_history_id()
        ids: list[str]
        if mailbox.history_id:
            try:
                ids, new_cursor = await reader.history_added(mailbox.history_id)
            except HistoryExpired:
                ids = await reader.list_recent(LOOKBACK_DAYS, MAX_PER_RUN)
        else:
            ids = await reader.list_recent(LOOKBACK_DAYS, MAX_PER_RUN)

        for message_id in ids[:MAX_PER_RUN]:
            raw = await reader.get_message(message_id)
            if raw is None:
                total.skipped += 1
                continue
            parsed = parse_gmail_message(raw)
            if parsed is None:
                total.skipped += 1
                continue
            try:
                async with session.begin_nested():
                    r = await process_email(session, parsed, mailbox, internal)
            except Exception as exc:  # noqa: BLE001 - one bad message must not stop the run
                logger.warning("email_process_failed", mailbox=mailbox.address, error=str(exc))
                total.skipped += 1
                continue
            total.logged += r.logged
            total.unmatched += r.unmatched
            total.skipped += r.skipped

        mailbox.history_id = new_cursor
        mailbox.last_error = None
        mailbox.last_logged = total.logged
        mailbox.total_logged = (mailbox.total_logged or 0) + total.logged
    except Exception as exc:  # noqa: BLE001
        logger.error("mailbox_sync_failed", mailbox=mailbox.address, error=str(exc))
        mailbox.last_error = str(exc)[:1000]
    mailbox.last_sync_at = now
    await session.flush()
    return total


async def run_sync_once(session: AsyncSession, settings: Settings) -> dict[str, ProcessResult]:
    """Sync every enabled mailbox. No-op (empty) if Gmail is not configured."""
    info = load_service_account(settings)
    if info is None:
        return {}
    out: dict[str, ProcessResult] = {}
    mailboxes = (
        await session.execute(select(Mailbox).where(Mailbox.enabled.is_(True)))
    ).scalars().all()
    for mb in mailboxes:
        out[mb.address] = await sync_mailbox(session, GmailReader(info, mb.address), mb, settings)
        await session.commit()
    return out


async def run_forever(settings: Settings) -> None:
    """Background loop started with the API. A Postgres advisory lock means only
    one ECS task runs a cycle at a time; duplicates are harmless anyway because
    activities are unique per (customer, Message-ID)."""
    from sqlalchemy import text

    from neocloud.db.session import get_sessionmaker

    interval = max(30, settings.email_sync_interval_seconds)
    logger.info("email_sync_loop_started", interval=interval)
    while True:
        try:
            async with get_sessionmaker()() as session:
                locked = True
                if session.bind.dialect.name == "postgresql":
                    locked = bool(
                        (await session.execute(text("SELECT pg_try_advisory_lock(727401)"))).scalar()
                    )
                if locked:
                    try:
                        await run_sync_once(session, settings)
                    finally:
                        if session.bind.dialect.name == "postgresql":
                            await session.execute(text("SELECT pg_advisory_unlock(727401)"))
                            await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("email_sync_cycle_failed", error=str(exc))
        await asyncio.sleep(interval)
