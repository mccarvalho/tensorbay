"""Deal documents: generated from an opportunity, saved as DOCX, filed in Drive."""

import io
from types import SimpleNamespace

import docx
import pytest
from httpx import AsyncClient

from neocloud.core.config import Settings
from neocloud.domains.documents import generator, kb, render
from neocloud.domains.documents.service import BedrockDocumentService
from tests.test_drive import FakeDrive

V1 = "/v1"
MARKDOWN = (
    "# Reserved Capacity Proposal\n\n## Configuration\n\n| Field | Specification |\n|---|---|\n"
    "| GPU | NVIDIA B300 |\n| Capacity | 512 GPUs |\n\n- **Term:** 36 months\n- Billing basis 730 hours\n\n"
    "1. First clause\n2. Second clause\n\nPlain paragraph with [TO BE COMPLETED].\n"
)


def _msa_template() -> bytes:
    d = docx.Document()
    d.add_paragraph("[CUSTOMER LEGAL NAME]")
    d.add_paragraph("Reference: TB-MSA-______-______")
    p = d.add_paragraph()
    p.add_run("registered office, [Custo").bold = True  # a placeholder split across runs
    p.add_run("mer legal name] ")
    p.add_run("registration number [●]")
    d.add_paragraph("Order Form No. ______ under the MSA")
    d.add_paragraph("and [Customer legal name], a [company form] organized under the laws of [jurisdiction], "
                    "with its registered office at [address], represented by [name], [title] (\"Customer\").")
    t = d.add_table(rows=0, cols=2)
    for k, v in [
        ("Item", "Specification"), ("Customer", "[Legal name, form, jurisdiction]"),
        ("Platform", "☐ NVIDIA HGX B200   ☐ NVIDIA HGX B300 (air-cooled)   ☐ Other: __________"),
        ("Quantity", "______ nodes / racks · ______ GPUs · ______ CPUs"),
        ("Per node or rack", "[GPUs per node]"),
        ("Compute fabric", "☐ NVIDIA Quantum InfiniBand (NDR)   ☐ RoCE v2 Ethernet   · approx. ______ Gb/s per GPU"),
        ("Storage", "Shared high-performance storage approx. ______ TB usable; local NVMe per node"),
        ("Connectivity", "Dedicated internet ______ Gb/s with ______ TB per month egress allowance; VPN on request"),
        ("Operating environment", "Linux operating system image, NVIDIA drivers, CUDA toolkit"),
        ("Customer technical contacts", "______"), ("Customer billing contact", "______"),
        ("Facility", "Region (if agreed): __________"),
        ("Target Service Commencement Date", "____ / ____ / ______ (Section 3)"),
        ("Term", "______ months from the Service Commencement Date"), ("Rate", "US$ ______ per GPU-hour"),
        ("Committed Value", "US$ ____ (____)"),
        ("Security (if any)", "☐ None   ☐ Escrow of US$ ________ (Schedule D, Part 2)"),
        ("Payment instructions", "Reference: Order Form No. ______"),
        ("Special terms (if any)", "______"),
    ]:
        r = t.add_row().cells
        r[0].text, r[1].text = k, v
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


class FakeKb:
    def template(self, name):
        return _msa_template()

    def text_names(self):
        return ["TensorBay_Spec_NVIDIA_HGX_B300_Air-Cooled", "TensorBay_Proposal_Goodfire_B300", "TensorBay_MSA_Standard_Form"]

    def text(self, name, limit=None):
        return f"text of {name}"


@pytest.fixture
def env(monkeypatch):
    store: dict[str, bytes] = {}
    prompts: list[tuple[str, str]] = []
    st = Settings(documents_bucket="docs", bedrock_model_id="test-model")
    monkeypatch.setattr(generator, "get_settings", lambda: st)
    monkeypatch.setattr("neocloud.domains.documents.router.get_settings", lambda: st)
    monkeypatch.setattr(kb, "get_kb", lambda: FakeKb())

    def converse(self, **kw):
        system, user = kw["system"][0]["text"], kw["messages"][0]["content"][0]["text"]
        prompts.append((system, user))
        if "ONE line" in system:
            return {"output": {"message": {"content": [{"text": "8 GPUs, 288 GB HBM3e each, 2x Xeon, 2 TB, NVLink 5"}]}}}
        return {"output": {"message": {"content": [{"text": MARKDOWN}]}}}

    monkeypatch.setattr(BedrockDocumentService, "_converse", converse)
    monkeypatch.setattr(BedrockDocumentService, "_put_object", lambda self, **kw: store.__setitem__(kw["Key"], kw["Body"]))

    class S3:
        def get_object(self, Bucket, Key):  # noqa: N803
            return {"Body": io.BytesIO(store[Key])}

    monkeypatch.setattr(BedrockDocumentService, "_s3_client", lambda self: S3())
    drive = FakeDrive()
    conn = SimpleNamespace(root_folder_id="ROOTFOLDER123", needs_reconnect=False)
    state = {"connected": True}

    async def get_conn(session):
        return conn

    monkeypatch.setattr(generator.drive_service, "get_connection", get_conn)
    monkeypatch.setattr(generator.drive_service, "make_drive", lambda s, c: drive if state["connected"] else None)
    return SimpleNamespace(store=store, prompts=prompts, drive=drive, state=state)


async def _deal(client: AsyncClient, short: str | None = "Positivo B300", escrow: bool = True) -> dict:
    cust = (await client.post(f"{V1}/customers", json={
        "legal_name": "Foxgaroo Ltda", "status": "PROSPECT", "country": "BR", "tax_id": "12.345.678/0001-90",
    })).json()
    await client.post(f"{V1}/customers/{cust['id']}/contacts", json={
        "type": "EXECUTIVE", "name": "Ana Souza", "role": "CEO", "email": "ana@foxgaroo.com"})
    opp = (await client.post(f"{V1}/sales/opportunities", json={
        "customer_id": cust["id"], "gpu_model": "B300", "quantity": 512, "duration_months": 36,
        "commercial_model": "GPU_MONTHLY", "expected_mrr": "1000000", "probability": 50, "short_name": short,
        "escrow_required": escrow, "expected_start": "2027-01-28", "region": "Brazil (São Paulo)",
    })).json()
    return opp


async def _generate(client, opp, doc_type="PROPOSAL", notes=None):
    r = await client.post(f"{V1}/documents/generate-for-opportunity",
                          json={"opportunity_id": opp["id"], "doc_type": doc_type, "notes": notes})
    assert r.status_code == 202, r.text
    docs = (await client.get(f"{V1}/documents/opportunity/{opp['id']}")).json()
    return r.json(), next(d for d in docs if d["id"] == r.json()["id"])


def _text(data: bytes) -> str:
    d = docx.Document(io.BytesIO(data))
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        parts += [c.text for row in t.rows for c in row.cells]
    return "\n".join(parts)


async def test_proposal_is_generated_downloaded_and_filed_in_drive(client, env):
    opp = await _deal(client)
    started, doc = await _generate(client, opp, notes="Escrow agent: JPMorgan")
    assert started["status"] == "GENERATING" and started["version"] == 1
    assert doc["status"] == "GENERATED", doc
    assert doc["file_name"].startswith("Proposal - Foxgaroo Ltda - v1 - ") and doc["file_name"].endswith(".docx")
    # The prompt carries the deal data, the reviewer notes and the knowledge base, with TensorBay branding.
    system, user = env.prompts[-1]
    assert "TensorBay" in system and "NeoCloud" not in system
    assert "Foxgaroo Ltda" in user and "Escrow agent: JPMorgan" in user and "text of TensorBay_Spec_NVIDIA_HGX_B300" in user
    assert '"gpus": 512' in user and '"implied_rate_usd_per_gpu_hour": "2.6755"' in user
    # DOCX: stored in S3 and downloadable.
    r = await client.get(f"{V1}/documents/{doc['id']}/download")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert doc["file_name"] in r.headers["content-disposition"]
    text = _text(r.content)
    assert "Reserved Capacity Proposal" in text and "512 GPUs" in text and "36 months" in text
    assert '"reference": "TB-PROP-POSITIVO-' in user  # the AI is given a ready-made document number
    # Filed in Drive: Clients/<customer>/YYYY-MM-<short name>/Proposal/
    (parent, name, content), = env.drive.uploads
    assert name == doc["file_name"] and content == r.content
    path = env.drive.path_of(parent)
    assert path.startswith("CRM TensorBay/Clients/Foxgaroo Ltda/") and path.endswith("-Positivo B300/Proposal"), path
    assert doc["drive_url"] and doc["drive_error"] is None
    # A second generation is a new version in the same folder.
    _, v2 = await _generate(client, opp)
    assert v2["version"] == 2 and "v2" in v2["file_name"]
    assert len(env.drive.uploads) == 2 and env.drive.path_of(env.drive.uploads[1][0]) == path


async def test_msa_fills_the_standard_form_instead_of_rewriting_it(client, env):
    opp = await _deal(client)
    _, doc = await _generate(client, opp, doc_type="MSA", notes="Net 30 on the balance")
    assert doc["status"] == "GENERATED", doc
    assert len(env.prompts) == 1 and "ONE line" in env.prompts[0][0]  # AI only wrote the per-node spec line
    data = (await client.get(f"{V1}/documents/{doc['id']}/download")).content
    text = _text(data)
    assert "FOXGAROO LTDA" in text and "[Custo" not in text and "[Customer legal name]" not in text
    assert "registration number 12.345.678/0001-90" in text
    assert "TB-MSA-POSITIVO-" in text and "Order Form No. TB-MSA-POSITIVO-" in text
    assert "☒ NVIDIA HGX B300 (air-cooled)" in text and "☐ NVIDIA HGX B200" in text
    assert "64 nodes / racks · 512 GPUs · ______ CPUs" in text
    assert "8 GPUs, 288 GB HBM3e each" in text
    assert "Region (if agreed): Brazil (São Paulo)" in text and "28 / 01 / 2027" in text
    assert "36 months from" in text and "US$ 2.6755 per GPU-hour" in text
    assert "US$ 36,000,000.00 (512 GPUs × 26,280 hours × Rate)" in text
    assert "☒ Escrow of US$ ________" in text and "☐ None" in text
    assert "[Draft note, to be reviewed] Net 30 on the balance" in text


async def test_msa_without_escrow_ticks_none(client, env):
    opp = await _deal(client, escrow=False)
    _, doc = await _generate(client, opp, doc_type="MSA")
    text = _text((await client.get(f"{V1}/documents/{doc['id']}/download")).content)
    assert "☒ None" in text and "☐ Escrow of US$" in text


async def test_drive_not_connected_keeps_the_document_and_retry_files_it(client, env):
    env.state["connected"] = False
    opp = await _deal(client, short=None)
    _, doc = await _generate(client, opp, doc_type="ORDER_FORM")
    assert doc["status"] == "GENERATED" and doc["drive_url"] is None
    assert "not connected" in doc["drive_error"]
    env.state["connected"] = True
    r = await client.post(f"{V1}/documents/{doc['id']}/save-to-drive")
    assert r.status_code == 200 and r.json()["drive_url"] and r.json()["drive_error"] is None
    path = env.drive.path_of(env.drive.uploads[0][0])
    assert path.endswith("-B300-512/Order Form"), path  # no short name: <model>-<qty>


async def test_model_failure_marks_the_document_failed_and_blocks_approval(client, env, monkeypatch):
    def boom(self, **kw):
        raise RuntimeError("AccessDeniedException: model access")

    monkeypatch.setattr(BedrockDocumentService, "_converse", boom)
    opp = await _deal(client)
    _, doc = await _generate(client, opp)
    assert doc["status"] == "FAILED" and "AccessDeniedException" in doc["error"]
    assert (await client.post(f"{V1}/documents/{doc['id']}/approve")).status_code == 409
    assert env.drive.uploads == []


async def test_unknown_opportunity_and_listing(client, env):
    r = await client.post(f"{V1}/documents/generate-for-opportunity", json={"opportunity_id": "nope", "doc_type": "NDA"})
    assert r.status_code == 404
    assert (await client.get(f"{V1}/documents/opportunity/nope")).json() == []


async def test_nda_fills_party_b(client, env, monkeypatch):
    d = docx.Document()
    d.add_paragraph("Reference: TB-NDA-______-______")
    d.add_paragraph("Purpose: ______________________________________________________________")
    d.add_paragraph("PARTY B: ____________________________")
    t = d.add_table(rows=2, cols=4)
    for i, v in enumerate(["Party", "Legal name", "Address", "Contact"]):
        t.cell(0, i).text = v
    for i, v in enumerate(["Party B", "", "", ""]):
        t.cell(1, i).text = v
    buf = io.BytesIO()
    d.save(buf)
    monkeypatch.setattr(FakeKb, "template", lambda self, name: buf.getvalue())
    opp = await _deal(client)
    _, doc = await _generate(client, opp, doc_type="NDA")
    text = _text((await client.get(f"{V1}/documents/{doc['id']}/download")).content)
    assert "TB-NDA-POSITIVO-" in text and "PARTY B: Foxgaroo Ltda" in text
    assert "Purpose: Evaluation and negotiation of dedicated GPU compute capacity (512 × B300)" in text
    assert "Brazil" in text and "Ana Souza, CEO, ana@foxgaroo.com" in text
    assert env.prompts == []  # no AI involved


def test_markdown_renders_headings_tables_lists_and_bold():
    data = render.markdown_to_docx(MARKDOWN + "\n**Bold line** and text\n*Italic note, not a bullet.*\n2 * 3 * 4 stays\n", "Test")
    d = docx.Document(io.BytesIO(data))
    styles = [p.style.name for p in d.paragraphs]
    assert "Title" in styles and "Heading 2" in styles and "List Bullet" in styles and "List Number" in styles
    assert len(d.tables) == 1 and d.tables[0].cell(1, 1).text == "NVIDIA B300"
    assert any(r.bold and r.text == "Term:" for p in d.paragraphs for r in p.runs)
    assert any(r.italic and r.text == "Italic note, not a bullet." for p in d.paragraphs for r in p.runs)
    assert any(p.text == "2 * 3 * 4 stays" for p in d.paragraphs)
    assert "TensorBay" in d.sections[0].header.paragraphs[0].text
    assert "Confidential" in d.sections[0].footer.paragraphs[0].text


def test_replace_spanning_runs_keeps_the_first_runs_format():
    d = docx.Document()
    p = d.add_paragraph()
    p.add_run("Dear ").italic = True
    p.add_run("[CUS").bold = True
    p.add_run("TOMER]")
    assert render.replace_in_paragraph(p, "[CUSTOMER]", "ACME")
    assert p.text == "Dear ACME" and p.runs[1].bold and p.runs[1].text == "ACME"
