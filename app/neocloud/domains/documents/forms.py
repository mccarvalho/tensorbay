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


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _person(name: str | None, email: str | None, phone: str | None = None) -> str | None:
    bits = [x for x in (name, email, phone) if x]
    return ", ".join(bits) or None


def fill_msa(template: bytes, ctx: dict[str, Any], per_node_spec: str | None, notes: str | None) -> bytes:
    doc = docx.Document(io.BytesIO(template))
    cust, opp = ctx["customer"], ctx["opportunity"]
    it: dict[str, Any] = ctx.get("customer_intake") or {}  # what the customer typed in the intake link
    ref = ctx["reference"].format(kind="MSA")
    name = it.get("legal_name") or cust["legal_name"]

    # Who the customer is: the intake wins over the CRM record, which is thinner.
    primary = next((c for c in ctx["contacts"] if c["type"] in ("EXECUTIVE", "COMMERCIAL")), None)
    party = {
        "form": it.get("company_form"),
        "jurisdiction": it.get("jurisdiction") or cust.get("country_name"),
        "reg": it.get("registration_number") or cust.get("tax_id"),
        "address": _one_line(it["registered_address"]) if it.get("registered_address") else None,
        "signatory": it.get("signatory_name") or (primary["name"] if primary else None),
        "title": it.get("signatory_title") or (primary.get("role") if primary else None),
    }
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
            pairs.append((placeholder, party[key]))
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

        legal = name
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
        start = opp.get("expected_start") or (it.get("preferred_start_date") if it else None)
        put("Target Service Commencement Date",
            lambda x: x.replace("____ / ____ / ______", _fmt_date(start)) if start else x)
        put("Term", lambda x: x.replace("______ months", f"{opp['term_months']} months", 1))
        put("Rate", lambda x: x.replace("US$ ______", f"US$ {opp['implied_rate_usd_per_gpu_hour']}", 1))
        hours = opp["gpu_hours_per_month_basis"] * opp["term_months"]
        put("Committed Value", lambda x: f"US$ {opp['committed_value_usd']} ({opp['gpus']} GPUs × {hours:,} hours × Rate)")
        put("Security", lambda x: _tick(x, "Escrow of US$ ________ (Schedule D, Part 2)") if opp["escrow_required"]
            else _tick(x, "None"))
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
            put("Special terms", lambda _x: " ".join(special))
    return render.docx_bytes(doc)


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
