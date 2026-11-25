"""Order Form intake: link tokens, expiry, and the 'customer filled it in' email."""

import hashlib
import html
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.core.mail import ses_source
from neocloud.domains.emailsync import oauth
from neocloud.domains.intake.models import IntakeStatus, OrderFormIntake

logger = get_logger(__name__)

LINK_DAYS = 14


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def is_expired(intake: OrderFormIntake) -> bool:
    return _aware(intake.expires_at) < datetime.now(UTC)


def reveal_token(settings: Settings, intake: OrderFormIntake) -> str | None:
    if intake.status == IntakeStatus.REVOKED or not intake.token_enc:
        return None
    try:
        return oauth.decrypt_token(settings, intake.token_enc)
    except Exception:  # noqa: BLE001 - no key configured
        return None


async def create_link(session: AsyncSession, settings: Settings, opportunity_id: str, actor: str) -> tuple[OrderFormIntake, str]:
    """A fresh link. Links still waiting for the customer are revoked; submitted data is kept."""
    for old in (
        await session.execute(
            select(OrderFormIntake).where(
                OrderFormIntake.opportunity_id == opportunity_id, OrderFormIntake.status == IntakeStatus.PENDING
            )
        )
    ).scalars():
        old.status, old.updated_by = IntakeStatus.REVOKED, actor
    token = new_token()
    try:
        enc: str | None = oauth.encrypt_token(settings, token)
    except Exception:  # noqa: BLE001 - key not configured: the link is shown once only
        enc = None
    intake = OrderFormIntake(
        opportunity_id=opportunity_id, token_hash=hash_token(token), token_enc=enc,
        status=IntakeStatus.PENDING, expires_at=datetime.now(UTC) + timedelta(days=LINK_DAYS),
        created_by=actor, updated_by=actor,
    )
    session.add(intake)
    await session.flush()
    return intake, token


async def by_token(session: AsyncSession, token: str) -> OrderFormIntake | None:
    return (
        await session.execute(select(OrderFormIntake).where(OrderFormIntake.token_hash == hash_token(token)))
    ).scalars().first()


async def latest_submitted(session: AsyncSession, opportunity_id: str) -> OrderFormIntake | None:
    return (
        await session.execute(
            select(OrderFormIntake)
            .where(OrderFormIntake.opportunity_id == opportunity_id, OrderFormIntake.status == IntakeStatus.SUBMITTED)
            .order_by(OrderFormIntake.submitted_at.desc())
            .limit(1)
        )
    ).scalars().first()


# --------------------------------------------------------------------------- #
# Email to the commercial owner
# --------------------------------------------------------------------------- #
@dataclass
class SubmittedNotice:
    opportunity_id: str
    opportunity_label: str
    customer_name: str
    signatory: str
    signatory_email: str
    gpu_model: str
    quantity: int


def recipients_for(settings: Settings, owner_email: str | None) -> list[str]:
    if owner_email:
        return [owner_email]
    return [e.strip() for e in settings.lead_alert_emails.split(",") if e.strip()]


def send_submitted_email(settings: Settings, notice: SubmittedNotice, recipients: list[str]) -> None:
    """Best-effort SES email. Never raises. Customer-supplied text is escaped."""
    if not settings.ses_from_email or not recipients:
        logger.info("intake_email_skipped", opportunity_id=notice.opportunity_id)
        return
    e = html.escape
    link = f"{settings.app_base_url.rstrip('/')}/opportunities/{notice.opportunity_id}#documents"

    def row(label: str, value: object) -> str:
        return (
            f'<tr><td style="padding:6px 12px 6px 0;color:#B9A9D6;font-size:13px;white-space:nowrap;">{e(label)}</td>'
            f'<td style="padding:6px 0;color:#ffffff;font-size:14px;">{e(str(value))}</td></tr>'
        )

    body = f"""\
<div style="margin:0;padding:0;background:#0D0221;font-family:Inter,Segoe UI,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:20px;font-weight:800;color:#ffffff;">TensorBay</div>
      <div style="font-size:11px;letter-spacing:3px;color:#B9A9D6;text-transform:uppercase;margin-top:4px;">GPU Control Plane</div>
    </div>
    <div style="background:#1a0a3a;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 12px;font-size:20px;color:#ffffff;">Order Form data received</h1>
      <p style="margin:0 0 16px;color:#B9A9D6;font-size:14px;">{e(notice.customer_name)} filled in the data for the Order Form. The MSA can now be generated.</p>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        {row("Opportunity", notice.opportunity_label)}
        {row("Capacity", f"{notice.quantity:,} x {notice.gpu_model}")}
        {row("Signatory", notice.signatory)}
        {row("Signatory email", notice.signatory_email)}
      </table>
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="margin:18px 0 0;"><tr>
        <td align="center" bgcolor="#00D4FF" style="background-color:#00D4FF;border-radius:12px;">
          <a href="{e(link)}" style="display:block;text-align:center;color:#0D0221;font-weight:700;text-decoration:none;padding:14px 20px;font-size:15px;">Review and generate the MSA &rarr;</a>
        </td></tr></table>
    </div>
  </div>
</div>"""
    text = (
        f"Order Form data received\n\n{notice.customer_name} filled in the data for the Order Form. "
        f"The MSA can now be generated.\n\nOpportunity: {notice.opportunity_label}\n"
        f"Capacity: {notice.quantity:,} x {notice.gpu_model}\nSignatory: {notice.signatory} <{notice.signatory_email}>\n\nOpen: {link}\n"
    )
    subject = ("[Order Form data received] " + notice.customer_name).replace("\r", " ").replace("\n", " ")[:120]
    try:
        kwargs: dict = {
            "Source": ses_source(settings),
            "Destination": {"ToAddresses": recipients},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Html": {"Data": body, "Charset": "UTF-8"}, "Text": {"Data": text, "Charset": "UTF-8"}},
            },
        }
        if settings.ses_configuration_set:
            kwargs["ConfigurationSetName"] = settings.ses_configuration_set
        boto3.client("ses", region_name=settings.aws_region).send_email(**kwargs)
        logger.info("intake_email_sent", opportunity_id=notice.opportunity_id, recipients=len(recipients))
    except Exception as exc:  # noqa: BLE001 - never fail the customer's submission on email
        logger.warning("intake_email_failed", opportunity_id=notice.opportunity_id, error=str(exc))
