"""Facts about a deal, gathered from the CRM, used to fill and ground documents."""

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from neocloud.domains.customers.models import Contact, Customer
from neocloud.domains.sales.models import Opportunity, Quote

GPU_HOURS_PER_MONTH = 730  # TensorBay billing basis
TENSORBAY = {
    "legal_name": "TensorBay Technology, LLC",
    "jurisdiction": "Delaware, USA",
    "registered_office": "8 The Green, Suite R, Dover, Delaware 19901",
    "principal_office": "7345 W Sand Lake Road, Suite 210, Orlando, Florida 32819",
    "signatory": "Bruno da Cruz Ramos, Chief Operating Officer",
    "email": "tensorbay@tensorbay.io",
}

COUNTRIES = {
    "BR": "Brazil", "US": "the United States of America", "CN": "the People's Republic of China",
    "SG": "Singapore", "ID": "Indonesia", "GB": "the United Kingdom", "CA": "Canada", "DE": "Germany",
}


def money(value: Decimal | float | int, places: int = 2) -> str:
    q = Decimal(1).scaleb(-places)
    return f"{Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP):,.{places}f}"


def reconciled_rate(committed: Decimal, gpus: int, term_months: int) -> str:
    """The GPU-hour rate with the fewest decimals (2 to 6) for which GPUs x hours x Rate
    reproduces the Committed Value to within US$5, so the Order Form adds up on its face.
    A negotiated rate such as 5.06 comes out exact; a rate derived from an MRR may need 6."""
    hours = GPU_HOURS_PER_MONTH * term_months
    if not gpus or not hours:
        return "0.00"
    exact = committed / (gpus * hours)
    for places in range(2, 7):
        r = exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        if abs(r * gpus * hours - committed) <= 5:
            return f"{r:.{places}f}"
    return f"{exact.quantize(Decimal(1).scaleb(-6), rounding=ROUND_HALF_UP):.6f}"


def gpus_per_unit(gpu_model: str) -> int:
    """GPUs in one node (8) or one NVL72 rack (72)."""
    m = gpu_model.upper().replace(" ", "")
    return 72 if "NVL72" in m or m.startswith(("GB200", "GB300")) else 8


def short_code(opp: Opportunity, customer: Customer) -> str:
    base = (opp.short_name or customer.trading_name or customer.legal_name or "DEAL").upper()
    code = re.sub(r"[^A-Z0-9]", "", base)[:8]
    return code or "DEAL"


async def load_deal(session: AsyncSession, opportunity_id: str) -> tuple[Opportunity, Customer, list[Contact], Quote | None]:
    opp = await session.get(Opportunity, opportunity_id)
    if opp is None:
        raise LookupError("Opportunity not found")
    customer = await session.get(Customer, opp.customer_id)
    if customer is None:
        raise LookupError("Customer not found")
    contacts = list(
        (await session.execute(select(Contact).where(Contact.customer_id == customer.id).order_by(Contact.created_at)))
        .scalars().all()
    )
    quote = (
        await session.execute(
            select(Quote).where(Quote.opportunity_id == opp.id).options(selectinload(Quote.items))
            .order_by(Quote.created_at.desc()).limit(1)
        )
    ).scalars().first()
    return opp, customer, contacts, quote


def build_context(opp: Opportunity, customer: Customer, contacts: list[Contact], quote: Quote | None) -> dict[str, Any]:
    qty = opp.quantity
    term = quote.term_months if quote else opp.duration_months
    per_unit = gpus_per_unit(opp.gpu_model)
    mrr = Decimal(opp.expected_mrr)
    rate = (mrr / (qty * GPU_HOURS_PER_MONTH)) if qty else Decimal(0)
    committed = Decimal(quote.total_amount) if quote and quote.total_amount else mrr * term
    ctx: dict[str, Any] = {
        "tensorbay": TENSORBAY,
        "customer": {
            "legal_name": customer.legal_name, "trading_name": customer.trading_name,
            "tax_id": customer.tax_id, "country": customer.country,
            "country_name": COUNTRIES.get((customer.country or "").upper()), "industry": customer.industry,
        },
        "contacts": [
            {"name": c.name, "role": c.role, "type": str(c.type), "email": c.email, "phone": c.phone}
            for c in contacts
        ],
        "opportunity": {
            "short_name": opp.short_name, "gpu_model": opp.gpu_model, "gpus": qty,
            "nodes_or_racks": -(-qty // per_unit), "gpus_per_node_or_rack": per_unit,
            "term_months": term, "commercial_model": opp.commercial_model, "region": opp.region,
            "expected_start": opp.expected_start.isoformat() if opp.expected_start else None,
            "expected_mrr_usd": money(mrr), "implied_rate_usd_per_gpu_hour": reconciled_rate(committed, qty, term),
            "gpu_hours_per_month_basis": GPU_HOURS_PER_MONTH,
            "committed_value_usd": money(committed),
            "escrow_required": opp.escrow_required, "stage": str(opp.sales_stage),
            "first_delivery_date": (opp.first_delivery_date or opp.expected_start).isoformat() if (opp.first_delivery_date or opp.expected_start) else None,
            "latest_delivery_date": (opp.latest_delivery_date or opp.first_delivery_date or opp.expected_start).isoformat()
            if (opp.latest_delivery_date or opp.first_delivery_date or opp.expected_start) else None,
            "payment_structure": opp.payment_structure,
            "upfront_pct": f"{Decimal(opp.upfront_pct).normalize():f}" if opp.upfront_pct is not None else None,
            "upfront_usd": money(committed * Decimal(opp.upfront_pct) / 100) if opp.upfront_pct is not None else None,
            "balance_usd": money(committed - committed * Decimal(opp.upfront_pct) / 100) if opp.upfront_pct is not None else None,
            "account_owner": opp.account_owner, "next_action": opp.next_action,
        },
        "today": date.today().isoformat(),
        "reference": f"TB-{{kind}}-{short_code(opp, customer)}-{date.today():%Y%m}",
    }
    if quote:
        ctx["quote"] = {
            "number": quote.quote_number, "status": str(quote.status), "term_months": quote.term_months,
            "total_usd": money(quote.total_amount), "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            "sla": quote.sla,
            "items": [
                {"quantity": i.quantity, "unit_price_usd": money(i.unit_price), "discount_pct": str(i.discount_pct)}
                for i in quote.items
            ],
        }
    return ctx
