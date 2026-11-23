"""Fill TensorBay's standard DOCX forms from deal data.

The legal text of these forms is never rewritten: only placeholders and the Order
Form table are filled. Anything the CRM does not know is left as the form's own
blank so the reviewer sees what remains to be completed.
"""

import io
from datetime import date
from typing import Any

import docx

from neocloud.domains.documents import render


def _platform_label(gpu_model: str) -> str | None:
    m = gpu_model.upper().replace(" ", "").replace("-", "")
    if "GB300" in m:
        return "NVIDIA GB300 NVL72"
    if "GB200" in m:
        return "NVIDIA GB200 NVL72"
    if "VR200" in m or "VERARUBIN" in m:
        return "NVIDIA DGX VR200"
    if "B300" in m:
        return "NVIDIA HGX B300 (liquid-cooled)" if "LIQUID" in m else "NVIDIA HGX B300 (air-cooled)"
    if "B200" in m:
        return "NVIDIA HGX B200"
    return None


def _tick(text: str, label: str) -> str:
    return text.replace(f"☐ {label}", f"☒ {label}", 1)


def _fmt_date(iso: str | None) -> str | None:
    if not iso:
        return None
    d = date.fromisoformat(iso)
    return f"{d.day:02d} / {d.month:02d} / {d.year}"


def _contact_line(contacts: list[dict[str, Any]], *types: str) -> str | None:
    picked = [c for c in contacts if c["type"] in types] or []
    return "; ".join(f"{c['name']}" + (f", {c['role']}" if c["role"] else "") + (f", {c['email']}" if c["email"] else "")
                     for c in picked) or None


def fill_msa(template: bytes, ctx: dict[str, Any], per_node_spec: str | None, notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    cust, opp = ctx["customer"], ctx["opportunity"]
    ref = ctx["reference"].format(kind="MSA")
    name = cust["legal_name"]
    pairs: list[tuple[str, str]] = [
        ("[CUSTOMER LEGAL NAME]", name.upper()),
        ("[Customer legal name]", name),
        ("TB-MSA-______-______", ref),
    ]
    if cust.get("tax_id"):
        pairs.append(("registration number [●]", f"registration number {cust['tax_id']}"))
    if cust.get("country_name"):
        pairs.append(("[jurisdiction]", cust["country_name"]))
    primary = next((c for c in ctx["contacts"] if c["type"] in ("EXECUTIVE", "COMMERCIAL")), None)
    if primary:
        pairs += [("[name]", primary["name"])]
        if primary.get("role"):
            pairs.append(("[title]", primary["role"]))
    pairs.append(("Order Form No. ______", f"Order Form No. {ref}"))
    render.replace_everywhere(doc, pairs)

    t = render.table_by_header(doc, "Item", "Specification")
    if t is not None:
        def put(label: str, fn) -> None:  # noqa: ANN001
            row = render.row_by_label(t, label)
            if row is not None:
                new = fn(row.cells[1].text)
                if new is not None and new != row.cells[1].text:
                    render.set_cell_text(row.cells[1], new)

        legal = name + (f", {cust['country_name']}" if cust.get("country_name") else "")
        put("Customer", lambda _t: legal + (f", registration number {cust['tax_id']}" if cust.get("tax_id") else "")
            + ("" if cust.get("tax_id") else " [registration number and registered address to be completed]"))
        label = _platform_label(opp["gpu_model"])
        put("Platform", lambda x: _tick(x, label) if label else x.replace("☐ Other: __________", f"☒ Other: {opp['gpu_model']}"))
        put("Quantity", lambda x: x.replace("______ nodes / racks", f"{opp['nodes_or_racks']} nodes / racks", 1)
            .replace("______ GPUs", f"{opp['gpus']} GPUs", 1))
        if per_node_spec:
            put("Per node or rack", lambda _x: per_node_spec)
        put("Facility", lambda x: x.replace("Region (if agreed): __________", f"Region (if agreed): {opp['region']}")
            if opp.get("region") else x)
        put("Target Service Commencement Date",
            lambda x: x.replace("____ / ____ / ______", _fmt_date(opp["expected_start"])) if opp.get("expected_start") else x)
        put("Term", lambda x: x.replace("______ months", f"{opp['term_months']} months", 1))
        put("Rate", lambda x: x.replace("US$ ______", f"US$ {opp['implied_rate_usd_per_gpu_hour']}", 1))
        hours = opp["gpu_hours_per_month_basis"] * opp["term_months"]
        put("Committed Value", lambda x: f"US$ {opp['committed_value_usd']} ({opp['gpus']} GPUs × {hours:,} hours × Rate)")
        put("Security", lambda x: _tick(x, "Escrow of US$ ________ (Schedule D, Part 2)") if opp["escrow_required"]
            else _tick(x, "None"))
        put("Payment instructions", lambda x: x.replace("Order Form No. ______", f"Order Form No. {ref}"))
        tech = _contact_line(ctx["contacts"], "TECHNICAL")
        bill = _contact_line(ctx["contacts"], "BILLING", "FINANCE")
        if tech:
            put("Customer technical contacts", lambda _x: tech)
        if bill:
            put("Customer billing contact", lambda _x: bill)
        if notes:
            put("Special terms", lambda _x: f"[Draft note, to be reviewed] {notes}")
    return render.docx_bytes(doc)


def fill_nda(template: bytes, ctx: dict[str, Any], notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    cust, opp = ctx["customer"], ctx["opportunity"]
    ref = ctx["reference"].format(kind="NDA")
    purpose = notes or (
        f"Evaluation and negotiation of dedicated GPU compute capacity ({opp['gpus']} × {opp['gpu_model']})"
    )
    render.replace_everywhere(doc, [
        ("TB-NDA-______-______", ref),
        ("Purpose: ______________________________________________________________", f"Purpose: {purpose}"),
        ("PARTY B: ____________________________", f"PARTY B: {cust['legal_name']}"),
    ])
    parties = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "Party"), None)
    if parties is not None:
        row = render.row_by_label(parties, "Party B")
        if row is not None:
            render.set_cell_text(row.cells[1], cust["legal_name"] + (f", {cust['country_name']}" if cust.get("country_name") else ""))
            contact = _contact_line(ctx["contacts"], "EXECUTIVE", "COMMERCIAL")
            if contact:
                render.set_cell_text(row.cells[3], contact)
    return render.docx_bytes(doc)
