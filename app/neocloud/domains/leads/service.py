"""Lead services: ingest-token resolution, AM routing, new-lead notification."""

from __future__ import annotations

import html
import json
import time
from dataclasses import dataclass

import boto3
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger
from neocloud.domains.economics.models import RepStatus, RepType, SalesRep
from neocloud.domains.leads.models import OPEN_STATUSES, Lead
from neocloud.domains.leads.parsing import region_matches

logger = get_logger(__name__)

# Placeholder some environments may seed before a real token is set.
_PLACEHOLDERS = {"", "REPLACE_ME", "changeme"}
_TOKEN_TTL_SECONDS = 300
_token_cache: dict[str, tuple[float, str]] = {}


# --------------------------------------------------------------------------- #
# Ingest token
# --------------------------------------------------------------------------- #
def resolve_ingest_token(settings: Settings) -> str | None:
    """Return the expected ingest token, or ``None`` if not configured.

    Order: explicit ``LEAD_INGEST_TOKEN`` (tests/local) then Secrets Manager.
    Secrets Manager values are cached for a few minutes so a rotated token takes
    effect without a redeploy. Failures are never cached.
    """
    if settings.lead_ingest_token and settings.lead_ingest_token not in _PLACEHOLDERS:
        return settings.lead_ingest_token
    arn = settings.lead_ingest_secret_arn
    if not arn:
        return None

    now = time.monotonic()
    cached = _token_cache.get(arn)
    if cached and now - cached[0] < _TOKEN_TTL_SECONDS:
        return cached[1]

    try:
        client = boto3.client("secretsmanager", region_name=settings.aws_region)
        raw = client.get_secret_value(SecretId=arn)["SecretString"]
    except Exception as exc:  # noqa: BLE001
        logger.error("lead_ingest_secret_fetch_failed", error=str(exc))
        return None

    token: str | None
    try:
        parsed = json.loads(raw)
        token = parsed.get("token") if isinstance(parsed, dict) else str(parsed)
    except json.JSONDecodeError:
        token = raw
    token = (token or "").strip()
    if token in _PLACEHOLDERS:
        return None
    _token_cache[arn] = (now, token)
    return token


# --------------------------------------------------------------------------- #
# Routing
# --------------------------------------------------------------------------- #
async def pick_assignee(
    session: AsyncSession, region: str | None, country: str | None
) -> SalesRep | None:
    """Pick the Account Manager for a lead.

    Eligible: active reps flagged ``lead_eligible`` (portal users in the SALES or
    SALES_MANAGER role are synced to one - see ``sync_sales_reps``).

    Pool: eligible AMs whose configured regions cover the lead; if none do, active
    AMs with no regions configured (catch-alls); if none, every active AM. Within
    the pool the AM with the fewest open leads wins, then the one assigned a lead
    least recently, then by name - a stable, fair round-robin.
    """
    ams = (
        await session.execute(
            select(SalesRep).where(
                SalesRep.lead_eligible.is_(True),
                SalesRep.type != RepType.FINDER,
                SalesRep.status == RepStatus.ACTIVE,
            )
        )
    ).scalars().all()
    if not ams:
        return None

    pool = [r for r in ams if region_matches(r.regions, region, country)]
    if not pool:
        pool = [r for r in ams if not (r.regions or "").strip()]
    if not pool:
        pool = list(ams)

    ids = [r.id for r in pool]
    open_counts = dict(
        (
            await session.execute(
                select(Lead.assigned_rep_id, func.count(Lead.id))
                .where(Lead.assigned_rep_id.in_(ids), Lead.status.in_(OPEN_STATUSES))
                .group_by(Lead.assigned_rep_id)
            )
        ).all()
    )
    last_assigned = dict(
        (
            await session.execute(
                select(Lead.assigned_rep_id, func.max(Lead.created_at))
                .where(Lead.assigned_rep_id.in_(ids))
                .group_by(Lead.assigned_rep_id)
            )
        ).all()
    )

    def sort_key(rep: SalesRep):
        last = last_assigned.get(rep.id)
        return (
            open_counts.get(rep.id, 0),
            last.timestamp() if last is not None else 0.0,
            rep.name.lower(),
        )

    return sorted(pool, key=sort_key)[0]


# --------------------------------------------------------------------------- #
# Sales users -> reps
# --------------------------------------------------------------------------- #
LEAD_ROLES = {"SALES", "SALES_MANAGER"}


@dataclass
class SyncResult:
    created: int = 0
    enabled: int = 0
    disabled: int = 0


def _norm(email: str | None) -> str:
    return (email or "").strip().lower()


async def sync_sales_reps(session: AsyncSession, users: list, actor: str) -> SyncResult:
    """Make every enabled SALES / SALES_MANAGER portal user a lead-eligible rep.

    ``users`` are admin users (``username, sub, email, name, enabled, roles``).
    * Eligible user with no rep -> an AM rep is created, linked by sub + email.
    * Eligible user with a rep (matched by sub, then email) -> flagged eligible and
      linked; the rep's type/status/regions are left alone.
    * A linked rep whose user lost the role, was disabled or deleted -> no longer
      eligible. Reps never linked to a portal user are never touched.
    Users are grouped by email so a native + Google twin of one person count once.
    """
    result = SyncResult()
    by_email: dict[str, list] = {}
    for u in users:
        if _norm(u.email):
            by_email.setdefault(_norm(u.email), []).append(u)

    reps = list((await session.execute(select(SalesRep))).scalars().all())
    seen_rep_ids: set[str] = set()

    for email, group in by_email.items():
        active = [u for u in group if u.enabled and LEAD_ROLES & set(u.roles or [])]
        subs = {u.sub for u in group if u.sub}
        rep = next((r for r in reps if r.cognito_sub and r.cognito_sub in subs), None)
        if rep is None:
            rep = next(
                (r for r in reps if _norm(r.email) == email and r.type != RepType.FINDER),
                None,
            )
        if rep is not None:
            seen_rep_ids.add(rep.id)

        if active:
            lead_user = active[0]
            if rep is None:
                rep = SalesRep(
                    name=(lead_user.name or email.split("@")[0]).strip(),
                    email=email,
                    type=RepType.AM,
                    status=RepStatus.ACTIVE,
                    cognito_sub=lead_user.sub,
                    lead_eligible=True,
                    created_by=actor,
                    updated_by=actor,
                )
                session.add(rep)
                reps.append(rep)
                result.created += 1
            else:
                if not rep.lead_eligible:
                    rep.lead_eligible = True
                    result.enabled += 1
                if not rep.cognito_sub:
                    rep.cognito_sub = lead_user.sub
                if not rep.email:
                    rep.email = email
                rep.updated_by = actor
        elif rep is not None and rep.lead_eligible:
            rep.lead_eligible = False
            rep.updated_by = actor
            result.disabled += 1

    # Linked reps whose user no longer exists at all.
    for rep in reps:
        if rep.id and rep.id not in seen_rep_ids and rep.cognito_sub and rep.lead_eligible:
            rep.lead_eligible = False
            rep.updated_by = actor
            result.disabled += 1

    await session.flush()
    return result


# --------------------------------------------------------------------------- #
# Notification
# --------------------------------------------------------------------------- #
@dataclass
class LeadNotice:
    """Plain data for the email so it can run after the DB session is closed."""

    lead_id: str
    name: str
    email: str
    company: str | None
    sku_of_interest: str | None
    gpu_count: int | None
    pricing_model_or_term: str | None
    region: str | None
    country: str | None
    message: str | None
    assignee_name: str | None
    is_repeat: bool
    needs_review: bool
    heading: str = "New pricing request"


def lead_recipients(settings: Settings, assignee_email: str | None) -> list[str]:
    extra = [e.strip() for e in settings.lead_alert_emails.split(",") if e.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for addr in ([assignee_email] if assignee_email else []) + extra:
        if addr and addr.lower() not in seen:
            seen.add(addr.lower())
            out.append(addr)
    return out


def send_new_lead_email(settings: Settings, notice: LeadNotice, recipients: list[str]) -> None:
    """Best-effort SES alert. Never raises. All lead-supplied text is escaped."""
    if not settings.ses_from_email or not recipients:
        logger.info(
            "new_lead_email_skipped",
            reason="no_ses_sender_or_recipients",
            lead_id=notice.lead_id,
        )
        return

    e = html.escape

    def row(label: str, value: object) -> str:
        shown = e(str(value)) if value not in (None, "") else "&mdash;"
        return (
            f'<tr><td style="padding:6px 12px 6px 0;color:#B9A9D6;font-size:13px;'
            f'vertical-align:top;white-space:nowrap;">{e(label)}</td>'
            f'<td style="padding:6px 0;color:#ffffff;font-size:14px;">{shown}</td></tr>'
        )

    where = " · ".join(p for p in (notice.region, notice.country) if p) or None
    flags = []
    if notice.is_repeat:
        flags.append("Repeat inquiry (an open lead from this email already exists)")
    if notice.needs_review:
        flags.append("Needs review (missing region or other details)")
    flag_html = "".join(
        f'<p style="margin:0 0 8px;color:#ffcc66;font-size:13px;">&#9888; {e(f)}</p>'
        for f in flags
    )
    link = f"{settings.app_base_url.rstrip('/')}/leads"
    button = (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'width="100%" style="margin:18px 0 0;"><tr>'
        '<td align="center" bgcolor="#00D4FF" style="background-color:#00D4FF;'
        'border-radius:12px;">'
        f'<a href="{e(link)}" style="display:block;text-align:center;color:#0D0221;'
        'font-weight:700;text-decoration:none;padding:14px 20px;font-size:15px;">'
        "Open in Leads &rarr;</a></td></tr></table>"
    )
    body = f"""\
<div style="margin:0;padding:0;background:#0D0221;font-family:Inter,Segoe UI,Arial,sans-serif;">
  <div style="max-width:560px;margin:0 auto;padding:32px 24px;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:20px;font-weight:800;color:#ffffff;">TensorBay</div>
      <div style="font-size:11px;letter-spacing:3px;color:#B9A9D6;text-transform:uppercase;margin-top:4px;">GPU Control Plane</div>
    </div>
    <div style="background:#1a0a3a;border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 16px;font-size:20px;color:#ffffff;">{e(notice.heading)}</h1>
      {flag_html}
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%">
        {row("Name", notice.name)}
        {row("Email", notice.email)}
        {row("Company", notice.company)}
        {row("Region", where)}
        {row("SKU of interest", notice.sku_of_interest)}
        {row("GPU count", notice.gpu_count)}
        {row("Pricing model / term", notice.pricing_model_or_term)}
        {row("Message", notice.message)}
        {row("Assigned to", notice.assignee_name or "Unassigned")}
      </table>
      {button}
    </div>
  </div>
</div>"""
    text = (
        f"{notice.heading}\n\nName: {notice.name}\nEmail: {notice.email}\n"
        f"Company: {notice.company or '-'}\nRegion: {where or '-'}\n"
        f"SKU: {notice.sku_of_interest or '-'}\nGPU count: {notice.gpu_count or '-'}\n"
        f"Pricing/term: {notice.pricing_model_or_term or '-'}\n"
        f"Message: {notice.message or '-'}\n"
        f"Assigned to: {notice.assignee_name or 'Unassigned'}\n\nOpen: {link}\n"
    )
    # Subject is header text: strip CR/LF so lead input can't inject headers.
    label = (notice.company or notice.name).replace("\r", " ").replace("\n", " ")[:80]
    subject = f"[New lead] {label}" + (f" - {where}" if where else "")
    try:
        ses = boto3.client("ses", region_name=settings.aws_region)
        kwargs: dict = {
            "Source": settings.ses_from_email,
            "Destination": {"ToAddresses": recipients},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": body, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        }
        if settings.ses_configuration_set:
            kwargs["ConfigurationSetName"] = settings.ses_configuration_set
        ses.send_email(**kwargs)
        logger.info("new_lead_email_sent", lead_id=notice.lead_id, recipients=len(recipients))
    except Exception as exc:  # noqa: BLE001 - never fail ingestion on email
        logger.warning("new_lead_email_failed", lead_id=notice.lead_id, error=str(exc))
