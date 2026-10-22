"""Economics domain services: deal economics + margin-warning notifications.

Keeps the business rules of the TensorBay Commission Plan in one place:
- ARR derivation from an opportunity (MRR x 12)
- gross profit = ARR x margin
- the sub-default-margin guardrail and the SES alert to the Account Manager
  and Super Admins when a deal closes below the plan's default margin.
"""

from __future__ import annotations

from decimal import Decimal

import boto3

from neocloud.core.config import Settings
from neocloud.core.logging import get_logger

logger = get_logger(__name__)

MONTHS_PER_YEAR = Decimal("12")


def annualize_mrr(expected_mrr: Decimal) -> Decimal:
    """ARR = MRR x 12."""
    return (Decimal(expected_mrr) * MONTHS_PER_YEAR).quantize(Decimal("0.01"))


def gross_profit(arr: Decimal, margin_pct: Decimal) -> Decimal:
    """Gross profit = ARR x margin."""
    return (Decimal(arr) * Decimal(margin_pct)).quantize(Decimal("0.01"))


def send_margin_warning_email(
    settings: Settings,
    *,
    deal_name: str,
    customer_id: str,
    arr: Decimal,
    margin_pct: Decimal,
    default_margin_pct: Decimal,
    recipients: list[str],
) -> None:
    """Alert the AM + Super Admin that a deal closed below the default margin.

    Best-effort: logs and swallows errors so it never blocks approval. Only
    sends when a verified SES sender and at least one recipient are configured.
    """
    if not settings.ses_from_email or not recipients:
        logger.info(
            "margin_warning_email_skipped",
            reason="no_ses_sender_or_recipients",
            deal=deal_name,
        )
        return

    margin_display = f"{(margin_pct * 100):.1f}%"
    default_display = f"{(default_margin_pct * 100):.1f}%"
    subject = f"[Margin warning] {deal_name} closed at {margin_display}"
    html = f"""\
<div style="margin:0;padding:0;background:#0D0221;font-family:Inter,Segoe UI,Arial,sans-serif;">
  <div style="max-width:520px;margin:0 auto;padding:32px 24px;">
    <div style="text-align:center;margin-bottom:24px;">
      <div style="font-size:20px;font-weight:800;color:#ffffff;letter-spacing:0.5px;">TensorBay</div>
      <div style="font-size:11px;letter-spacing:3px;color:#B9A9D6;text-transform:uppercase;margin-top:4px;">GPU Control Plane</div>
    </div>
    <div style="background:#2a0f1a;border:1px solid rgba(255,120,120,0.25);border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 12px;font-size:18px;color:#ff9a9a;">&#9888; Margin below target</h1>
      <p style="margin:0 0 16px;font-size:14px;line-height:1.6;color:#E6D9F2;">
        The deal <strong style="color:#ffffff;">{deal_name}</strong> (customer
        <strong style="color:#ffffff;">{customer_id}</strong>) is pending commission
        approval with a gross margin of <strong style="color:#ff9a9a;">{margin_display}</strong>,
        below the plan default of <strong style="color:#ffffff;">{default_display}</strong>.
      </p>
      <p style="margin:0;font-size:14px;line-height:1.6;color:#B9A9D6;">
        ARR: <strong style="color:#ffffff;">${arr:,.2f}</strong>. Please review the
        pricing and margin before approving in the Economics &rarr; Deals queue.
      </p>
    </div>
    <p style="text-align:center;font-size:11px;color:rgba(185,169,214,0.5);margin-top:24px;">
      TensorBay GPU Control Plane &middot; Automated margin guardrail alert.
    </p>
  </div>
</div>"""
    text = (
        f"Margin warning: {deal_name} (customer {customer_id}) is pending commission "
        f"approval at {margin_display} margin, below the {default_display} plan default. "
        f"ARR ${arr:,.2f}. Review pricing/margin before approving."
    )
    try:
        ses = boto3.client("ses", region_name=settings.aws_region)
        send_kwargs: dict = {
            "Source": settings.ses_from_email,
            "Destination": {"ToAddresses": recipients},
            "Message": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        }
        if settings.ses_configuration_set:
            send_kwargs["ConfigurationSetName"] = settings.ses_configuration_set
        ses.send_email(**send_kwargs)
        logger.info("margin_warning_email_sent", deal=deal_name, recipients=len(recipients))
    except Exception as exc:  # noqa: BLE001 - never block approval on email
        logger.warning("margin_warning_email_failed", deal=deal_name, error=str(exc))
