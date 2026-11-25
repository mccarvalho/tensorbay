"""Fill TensorBay's standard DOCX forms (package V4) from deal data.

The legal text of these forms is never rewritten: only placeholders, the Order Form
table and the escrow appendix are filled. Anything the CRM does not know is left as the
form's own blank so the reviewer sees what remains to be completed.

Forms: MSA (with its embedded Schedule A), Schedule A Order Form, Schedule D-1 Escrow
Agreement and the multilateral NDA.
"""

import io
from datetime import date
from typing import Any

import docx

from neocloud.domains.documents import render

PAYMENT_STRUCTURE = {
    "A": "A. Monthly installments",
    "B": "B. Quarterly installments + deposit",
    "C": "C. Monthly installments + Security",
    "D": "D. Other balance schedule",
}


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
    """TensorBay's date standard in documents: MM/DD/YYYY."""
    if not iso:
        return None
    d = date.fromisoformat(iso)
    return f"{d.month:02d}/{d.day:02d}/{d.year}"


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _person(name: str | None, email: str | None, phone: str | None = None) -> str | None:
    bits = [x for x in (name, email, phone) if x]
    return ", ".join(bits) or None


def _contact_line(contacts: list[dict[str, Any]], *types: str) -> str | None:
    picked = [c for c in contacts if c["type"] in types] or []
    return "; ".join(f"{c['name']}" + (f", {c['role']}" if c["role"] else "") + (f", {c['email']}" if c["email"] else "")
                     for c in picked) or None


def _party(ctx: dict[str, Any]) -> dict[str, str | None]:
    """Who the customer is: what they typed in the intake link wins over the CRM record."""
    cust = ctx["customer"]
    it: dict[str, Any] = ctx.get("customer_intake") or {}
    primary = next((c for c in ctx["contacts"] if c["type"] in ("EXECUTIVE", "COMMERCIAL")), None)
    return {
        "name": it.get("legal_name") or cust["legal_name"],
        "form": it.get("company_form"),
        "jurisdiction": it.get("jurisdiction") or cust.get("country_name"),
        "reg": it.get("registration_number") or cust.get("tax_id"),
        "address": _one_line(it["registered_address"]) if it.get("registered_address") else None,
        "signatory": it.get("signatory_name") or (primary["name"] if primary else None),
        "title": it.get("signatory_title") or (primary.get("role") if primary else None),
        "signatory_email": it.get("signatory_email") or (primary.get("email") if primary else None),
    }


def _of_ref(ctx: dict[str, Any]) -> str:
    return ctx["reference"].format(kind="OF")


# --------------------------------------------------------------------------- #
# Schedule A: the Order Form table (inside the MSA and as its own form)
# --------------------------------------------------------------------------- #
def _fill_schedule_a(doc, ctx: dict[str, Any], per_node_spec: str | None, notes: str | None) -> None:  # noqa: ANN001
    t = render.table_by_header(doc, "Item", "Specification")
    if t is None:
        return
    opp = ctx["opportunity"]
    it: dict[str, Any] = ctx.get("customer_intake") or {}
    party = _party(ctx)
    ref = _of_ref(ctx)

    def put(label: str, fn) -> None:  # noqa: ANN001
        row = render.row_by_label(t, label)
        if row is not None:
            new = fn(row.cells[1].text)
            if new is not None and new != row.cells[1].text:
                render.set_cell_text(row.cells[1], new)

    legal = party["name"] or ""
    if party["form"] and party["jurisdiction"]:
        legal += f", a {party['form']} organized under the laws of {party['jurisdiction']}"
    elif party["jurisdiction"]:
        legal += f", {party['jurisdiction']}"
    if party["reg"]:
        legal += f", registration number {party['reg']}"
    if party["address"]:
        legal += f", registered address {party['address']}"
    missing = [x for x, k in (("company form", "form"), ("registration number", "reg"), ("registered address", "address")) if not party[k]]
    put("Customer", lambda _t: legal + (f" [{', '.join(missing)} to be completed]" if missing else ""))

    label = _platform_label(opp["gpu_model"])
    put("Platform", lambda x: _tick(x, label) if label else x.replace("☐ Other: __________", f"☒ Other: {opp['gpu_model']}"))
    put("Quantity", lambda x: x.replace("______ nodes / racks", f"{opp['nodes_or_racks']} nodes / racks", 1)
        .replace("______ GPUs", f"{opp['gpus']} GPUs", 1))
    if per_node_spec:
        put("Per node or rack", lambda _x: per_node_spec)
    fabric = {"INFINIBAND": "NVIDIA Quantum InfiniBand (NDR)", "ROCE": "RoCE v2 Ethernet"}.get(it.get("compute_fabric") or "")
    if fabric:
        put("Compute fabric", lambda x: _tick(x, fabric))
    if it.get("shared_storage_tb") is not None:
        put("Storage", lambda x: x.replace("approx. ______ TB usable", f"approx. {it['shared_storage_tb']:,} TB usable", 1))

    def connectivity(x: str) -> str:
        if it.get("dedicated_internet_gbps") is not None:
            x = x.replace("______ Gb/s", f"{it['dedicated_internet_gbps']:,} Gb/s", 1)
        if it.get("monthly_egress_tb") is not None:
            x = x.replace("______ TB per month", f"{it['monthly_egress_tb']:,} TB per month", 1)
        return x

    put("Connectivity", connectivity)
    if it.get("os_image_notes"):
        put("Operating environment", lambda x: f"{x}. Customer requirements: {_one_line(it['os_image_notes'])}")
    region = opp.get("region") or it.get("region_preference")
    put("Facility", lambda x: x.replace("Region (if agreed): __________", f"Region (if agreed): {region}") if region else x)

    # V4: first and latest original delivery targets (they decide the upfront route, MSA 6.2).
    first = _fmt_date(opp.get("first_delivery_date") or (it.get("preferred_start_date") if it else None))
    latest = _fmt_date(opp.get("latest_delivery_date") or opp.get("first_delivery_date") or (it.get("preferred_start_date") if it else None))

    def targets(x: str) -> str:
        if first:
            x = x.replace("____ / ____ / ______", first, 1)
        if latest:
            x = x.replace("____ / ____ / ______", latest, 1)
        return x

    put("Target delivery date(s)", targets)
    put("Term", lambda x: x.replace("______ months", f"{opp['term_months']} months", 1))
    put("Rate", lambda x: x.replace("US$ ______", f"US$ {opp['implied_rate_usd_per_gpu_hour']}", 1))
    hours = opp["gpu_hours_per_month_basis"] * opp["term_months"]
    put("Committed Value", lambda _x: f"US$ {opp['committed_value_usd']} ({opp['gpus']} GPUs × {hours:,} hours × Rate)")

    if opp.get("payment_structure") in PAYMENT_STRUCTURE:
        structure = PAYMENT_STRUCTURE[opp["payment_structure"]]
        put("Payment Structure", lambda x: _tick(x, structure))
    if opp.get("upfront_pct"):
        put("Upfront Payment", lambda x: x.replace("______%", f"{opp['upfront_pct']}%", 1).replace("US$ __________", f"US$ {opp['upfront_usd']}", 1))
        put("Remaining payment schedule", lambda x: x.replace("US$ ______.", f"US$ {opp['balance_usd']}.", 1))

    def route(x: str) -> str:
        if opp["escrow_required"]:
            x = _tick(x, "Escrow (after cutoff)")
            if opp.get("upfront_usd"):
                x = x.replace("Escrow amount: US$ ______", f"Escrow amount: US$ {opp['upfront_usd']}", 1)
            return x
        return _tick(x, "Direct wire (latest target on/before cutoff)")

    put("Mandatory upfront route", route)
    put("Delivery plan", lambda x: _tick(x, "Single Cluster"))
    put("Payment instructions", lambda x: x.replace("Order Form No. ______", f"Order Form No. {ref}"))

    tech = _person(it.get("technical_contact_name"), it.get("technical_contact_email"), it.get("technical_contact_phone")) \
        or _contact_line(ctx["contacts"], "TECHNICAL")
    bill = _person(it.get("billing_contact_name"), it.get("billing_contact_email"), it.get("billing_contact_phone")) \
        or _contact_line(ctx["contacts"], "BILLING", "FINANCE")
    if tech:
        put("Customer technical contacts", lambda _x: tech)
    if bill:
        put("Customer billing contact", lambda _x: bill)

    special = []
    if notes:
        special.append(f"[Draft note, to be reviewed] {notes}")
    if it.get("allowed_ip_addresses"):
        special.append(f"Access from the customer's declared addresses: {_one_line(it['allowed_ip_addresses'])}")
    if it.get("additional_notes"):
        special.append(f"[Customer note, to be reviewed] {_one_line(it['additional_notes'])}")
    if special:
        # The row already carries standard wording about amendments: keep it, add the notes after.
        put("Special terms", lambda x: (x.strip("_ \n") + " " if x.strip("_ \n") else "") + " ".join(special))

    _fill_tranche_table(doc, ctx)


def _fill_tranche_table(doc, ctx: dict[str, Any]) -> None:  # noqa: ANN001
    """One Cluster: a single tranche row that carries the whole deal, plus the totals."""
    opp = ctx["opportunity"]
    table = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "Tranche"), None)
    if table is None or len(table.rows) < 3:
        return
    target = _fmt_date(opp.get("latest_delivery_date")) or ""
    upfront = opp.get("upfront_usd") or ""
    balance = opp.get("balance_usd") or ""
    first = ["1", f"{opp['gpus']:,}", target, opp["committed_value_usd"], upfront, balance]
    total = ["TOTAL", f"{opp['gpus']:,}", "", opp["committed_value_usd"], upfront, balance]
    for row, values in ((table.rows[1], first), (table.rows[-1], total)):
        for cell, value in zip(row.cells, values, strict=False):
            if value:
                render.set_cell_text(cell, value)


# --------------------------------------------------------------------------- #
# MSA
# --------------------------------------------------------------------------- #
def fill_msa(template: bytes, ctx: dict[str, Any], per_node_spec: str | None, notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    party = _party(ctx)
    name = party["name"] or ""
    ref = ctx["reference"].format(kind="MSA")
    pairs: list[tuple[str, str]] = [
        ("[CUSTOMER LEGAL NAME]", name.upper()),
        ("[Customer legal name]", name),
        ("TB-MSA-______-______", ref),
    ]
    if party["reg"]:
        pairs.append(("registration number [●]", f"registration number {party['reg']}"))
    for placeholder, key in (("[company form]", "form"), ("[jurisdiction]", "jurisdiction"), ("[address]", "address"),
                             ("[name]", "signatory"), ("[title]", "title")):
        if party[key]:
            pairs.append((placeholder, str(party[key])))
    # Longest blank first: "______" is a prefix of "__________".
    pairs += [("Order Form No. __________", f"Order Form No. {_of_ref(ctx)}"), ("Order Form No. ______", f"Order Form No. {_of_ref(ctx)}")]
    render.replace_everywhere(doc, pairs)
    _fill_schedule_a(doc, ctx, per_node_spec, notes)
    return render.docx_bytes(doc)


# --------------------------------------------------------------------------- #
# Schedule A as its own document
# --------------------------------------------------------------------------- #
def fill_order_form(template: bytes, ctx: dict[str, Any], per_node_spec: str | None, notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    party = _party(ctx)
    name = party["name"] or "Customer"
    ref = _of_ref(ctx)
    render.replace_everywhere(doc, [
        ("Order Form No. __________", f"Order Form No. {ref}"),
        ("Order Form No. ______", f"Order Form No. {ref}"),
        ("TensorBay Technology, LLC and Customer.", f"TensorBay Technology, LLC and {name}."),
        ("Order Form accepted for Customer", f"Order Form accepted for {name}"),
    ])
    _fill_schedule_a(doc, ctx, per_node_spec, notes)
    return render.docx_bytes(doc)


# --------------------------------------------------------------------------- #
# Schedule D-1: tripartite escrow agreement
# --------------------------------------------------------------------------- #
def fill_escrow(template: bytes, ctx: dict[str, Any], notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    opp = ctx["opportunity"]
    party = _party(ctx)
    ref = ctx["reference"].format(kind="ESC")
    of_ref = _of_ref(ctx)
    # Only the cover line: the same words recur, with a longer blank, in Appendix A.
    render.replace_everywhere(doc, [
        ("TB-ESC-____________  |  MSA date: ____________  |  Order Form No.: ____________",
         f"{ref}  |  MSA date: ____________  |  Order Form No.: {of_ref}"),
    ])

    appendix = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "Item"
                     and len(t.columns) == 2), None)
    if appendix is not None:
        def cell(label: str):  # noqa: ANN202
            row = render.row_by_label(appendix, label)
            return row.cells[1] if row is not None else None

        def fill(label: str, field: str, value: str | None) -> None:
            c = cell(label)
            if c is not None and value:
                render.fill_blank(c.paragraphs, field, value)

        fill("MSA and Order Form", "Order Form No.:", of_ref)
        fill("Customer / remitter", "Legal entity:", party["name"])
        fill("Customer / remitter", "Registered jurisdiction:", party["jurisdiction"])
        fill("Upfront Payment", "Committed Value (USD):", opp["committed_value_usd"])
        if opp.get("upfront_pct"):
            c = cell("Upfront Payment")
            if c is not None:
                render.fill_blank(c.paragraphs, "(% of Committed Value):", opp["upfront_pct"])
                for par in c.paragraphs:  # the blank is followed by a literal "%"
                    render.replace_in_paragraph(par, "%%", "%")
                render.fill_blank(c.paragraphs, "Agreed Upfront Payment (USD):", opp["upfront_usd"])
        latest = (opp.get("latest_delivery_date") or "")
        if latest:
            fill("Payment deadline", "latest target:", _fmt_date(latest))
        customer_contact = _person(party["signatory"], party["signatory_email"])
        fill("Verified contacts", "Customer:", customer_contact)

    # Execution block: the customer's signatory.
    sign = next((t for t in doc.tables if t.rows and t.rows[0].cells[0].text.strip() == "TensorBay Technology, LLC"), None)
    if sign is not None and len(sign.rows) > 1 and len(sign.rows[1].cells) > 1:
        cust_cell = sign.rows[1].cells[1]
        sign.rows[0].cells[1].paragraphs[0].runs[0].text = f"{party['name']} (Customer)" if party["name"] else "Customer"
        if party["signatory"]:
            render.fill_blank(cust_cell.paragraphs, "Name:", party["signatory"])
        if party["title"]:
            render.fill_blank(cust_cell.paragraphs, "Title:", party["title"])
    return render.docx_bytes(doc)


# --------------------------------------------------------------------------- #
# NDA
# --------------------------------------------------------------------------- #
def fill_nda(template: bytes, ctx: dict[str, Any], notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    cust, opp = ctx["customer"], ctx["opportunity"]
    it: dict[str, Any] = ctx.get("customer_intake") or {}
    cust = {**cust, "legal_name": it.get("legal_name") or cust["legal_name"]}
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
            if it.get("registered_address"):
                render.set_cell_text(row.cells[2], _one_line(it["registered_address"]))
            contact = _person(it.get("signatory_name"), it.get("notices_email")) or _contact_line(ctx["contacts"], "EXECUTIVE", "COMMERCIAL")
            if contact:
                render.set_cell_text(row.cells[3], contact)
    return render.docx_bytes(doc)
