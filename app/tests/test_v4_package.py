"""The real V4 contract package (MSA, Schedule A Order Form, Schedule D-1 Escrow Agreement).

The files are confidential and not in the repo: set TB_CONTRACT_PACKAGE to the folder to run this.
"""

import io
import os
import re
from pathlib import Path

import docx
import pytest

from neocloud.domains.documents import forms

PKG = os.environ.get("TB_CONTRACT_PACKAGE")
pytestmark = pytest.mark.skipif(not PKG or not Path(PKG).is_dir(), reason="TB_CONTRACT_PACKAGE not set")

CTX = {
    "customer": {"legal_name": "Foxgaroo Ltda", "tax_id": None, "country": "BR", "country_name": "Brazil"},
    "contacts": [],
    "customer_intake": {
        "legal_name": "Foxgaroo Ltda", "company_form": "limited liability company", "jurisdiction": "Brazil",
        "registration_number": "12.345.678/0001-90", "registered_address": "Av Paulista 1000\nSao Paulo",
        "signatory_name": "Ana Souza", "signatory_title": "CEO", "signatory_email": "ana@fox.com",
        "compute_fabric": "INFINIBAND", "shared_storage_tb": 500,
    },
    "opportunity": {
        "gpu_model": "B300", "gpus": 512, "nodes_or_racks": 64, "term_months": 36, "region": None,
        "first_delivery_date": "2027-01-30", "latest_delivery_date": "2027-06-30",
        "implied_rate_usd_per_gpu_hour": "2.6755", "gpu_hours_per_month_basis": 730,
        "committed_value_usd": "36,000,000.00", "escrow_required": True, "payment_structure": "A",
        "upfront_pct": "30", "upfront_usd": "10,800,000.00", "balance_usd": "25,200,000.00",
    },
    "reference": "TB-{kind}-FOXGAROO-202611",
}


def _text(data: bytes) -> str:
    d = docx.Document(io.BytesIO(data))
    out = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            seen: list[str] = []
            for c in r.cells:
                if c.text not in seen:
                    seen.append(c.text)
                    out.append(c.text)
    return "\n".join(out)


def _read(prefix: str) -> bytes:
    return next(Path(PKG).glob(f"{prefix}_*.docx")).read_bytes()


def test_msa_v4_is_filled_including_schedule_a():
    t = _text(forms.fill_msa(_read("01"), CTX, "8 GPUs per node", None))
    for needle in ["FOXGAROO LTDA", "TB-MSA-FOXGAROO-202611", "Order Form No. TB-OF-FOXGAROO-202611",
                   "a limited liability company organized under the laws of Brazil", "registration number 12.345.678/0001-90",
                   "☒ NVIDIA HGX B300 (air-cooled)", "☒ NVIDIA Quantum InfiniBand (NDR)", "approx. 500 TB usable",
                   "First target: 01/30/2027. Latest original target (all capacity): 06/30/2027.",
                   "Agreed advance: 30% of Committed Value = US$ 10,800,000.00", "☒ A. Monthly installments",
                   "☒ Escrow (after cutoff)", "Escrow amount: US$ 10,800,000.00 (= advance)",
                   "Committed Value less Upfront Payment = US$ 25,200,000.00.", "☒ Single Cluster"]:
        assert needle in t, needle
    assert "[CUSTOMER LEGAL NAME]" not in t and "[Customer legal name]" not in t


def test_order_form_v4_is_filled():
    t = _text(forms.fill_order_form(_read("02"), CTX, None, "net terms to confirm"))
    assert "Order Form No. TB-OF-FOXGAROO-202611 under the Master Services Agreement" in t
    assert "between TensorBay Technology, LLC and Foxgaroo Ltda." in t and "Order Form accepted for Foxgaroo Ltda" in t
    assert "US$ 36,000,000.00 (512 GPUs × 26,280 hours × Rate)" in t
    assert "Only amendments identifying the MSA section" in t and "[Draft note, to be reviewed] net terms to confirm" in t
    assert re.search(r"1\n512\n06/30/2027\n36,000,000.00\n10,800,000.00\n25,200,000.00", t)


def test_escrow_agreement_v4_is_filled_without_breaking_blanks_it_does_not_know():
    t = _text(forms.fill_escrow(_read("03"), CTX, None))
    assert "Reference: TB-ESC-FOXGAROO-202611  |  MSA date: ____________  |  Order Form No.: TB-OF-FOXGAROO-202611" in t
    assert "Order Form No.: TB-OF-FOXGAROO-202611  Order Effective Date: _____________" in t
    assert "Legal entity: Foxgaroo Ltda" in t and "Registered jurisdiction: Brazil" in t
    assert "Agreed Upfront Payment (% of Committed Value): 30%" in t and "Agreed Upfront Payment (USD): 10,800,000.00" in t
    assert "latest target: 06/30/2027" in t and "Customer: Ana Souza, ana@fox.com" in t
    assert "Foxgaroo Ltda (Customer)" in t and "Name: Ana Souza" in t and "Title: CEO" in t
    assert "Legal name: ___________________________________" in t  # the escrow agent is still to be completed
