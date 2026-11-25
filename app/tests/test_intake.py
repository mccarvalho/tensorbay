"""Order Form intake: a private link the customer fills in; the owner is told; documents use it."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from neocloud.core.config import Settings
from neocloud.domains.intake import router as intake_router
from neocloud.domains.intake import service
from neocloud.domains.intake.models import IntakeStatus, OrderFormIntake
from tests.test_deal_documents import _deal, _generate, _text, env  # noqa: F401 - env is a fixture

V1 = "/v1"
GOOD = {
    "legal_name": "Foxgaroo Ltda", "company_form": "limited liability company", "jurisdiction": "Brazil",
    "registration_number": "12.345.678/0001-90", "registered_address": "Av. Paulista 1000\nSão Paulo, SP",
    "signatory_name": "Ana Souza", "signatory_title": "CEO", "signatory_email": "ana@foxgaroo.com",
    "notices_email": "legal@foxgaroo.com",
    "technical_contact_name": "Tec Guy", "technical_contact_email": "tec@foxgaroo.com", "technical_contact_phone": "+55 11 5555",
    "billing_contact_email": "",
    "workload_description": "Pre-training a 70B model", "compute_fabric": "INFINIBAND",
    "shared_storage_tb": 500, "dedicated_internet_gbps": 10, "monthly_egress_tb": 20,
    "access_methods": ["SSH", "VPN"], "allowed_ip_addresses": "203.0.113.0/24",
    "os_image_notes": "Ubuntu 22.04", "preferred_start_date": "2027-02-01", "additional_notes": "Please call first",
    "confirm_accuracy": True,
}


@pytest.fixture
def mails(monkeypatch):
    sent: list[tuple] = []
    monkeypatch.setattr(service, "send_submitted_email", lambda settings, notice, rcpts: sent.append((notice, rcpts)))
    monkeypatch.setattr(intake_router.service, "send_submitted_email", lambda settings, notice, rcpts: sent.append((notice, rcpts)))
    return sent


async def _link(client: AsyncClient, opp_id: str) -> tuple[dict, str]:
    r = await client.post(f"{V1}/intake/opportunity/{opp_id}/link")
    assert r.status_code == 201, r.text
    return r.json(), r.json()["token"]


async def _owned_opp(client: AsyncClient) -> dict:
    cust = (await client.post(f"{V1}/customers", json={"legal_name": "Foxgaroo Ltda", "status": "PROSPECT"})).json()
    return (await client.post(f"{V1}/sales/opportunities", json={
        "customer_id": cust["id"], "gpu_model": "B300", "quantity": 512, "duration_months": 36,
        "commercial_model": "GPU_MONTHLY", "expected_mrr": "1000000", "probability": 50, "short_name": "Positivo B300",
        "account_owner": "Lizi", "account_owner_email": "lizi@tensorbay.io",
    })).json()


async def test_public_form_shows_the_deal_without_prices_and_submission_alerts_the_owner(client, mails):
    opp = await _owned_opp(client)
    _admin, token = await _link(client, opp["id"])
    r = await client.get(f"{V1}/public/intake/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING" and body["customer_name"] == "Foxgaroo Ltda"
    assert body["gpu_model"] == "B300" and body["quantity"] == 512 and body["contact_name"] == "Lizi"
    assert "1000000" not in r.text and "mrr" not in r.text.lower() and "price" not in r.text.lower()
    assert body["prefill"] == {"legal_name": "Foxgaroo Ltda"}

    done = await client.post(f"{V1}/public/intake/{token}", json=GOOD)
    assert done.status_code == 200 and done.json()["status"] == "SUBMITTED"
    # The commercial owner is told the MSA can be generated.
    (notice, recipients), = mails
    assert recipients == ["lizi@tensorbay.io"]
    assert notice.customer_name == "Foxgaroo Ltda" and "Ana Souza" in notice.signatory and notice.opportunity_id == opp["id"]
    # A submitted link shows nothing back and cannot be filled in twice.
    again = await client.get(f"{V1}/public/intake/{token}")
    assert again.json()["status"] == "SUBMITTED" and again.json()["prefill"] is None
    assert (await client.post(f"{V1}/public/intake/{token}", json=GOOD)).status_code == 409
    # Staff see the data.
    rows = (await client.get(f"{V1}/intake/opportunity/{opp['id']}")).json()
    assert rows[0]["status"] == "SUBMITTED" and rows[0]["data"]["signatory_name"] == "Ana Souza" and rows[0]["token"] is None


async def test_validation_rejects_missing_or_bad_fields_and_unknown_keys(client, mails):
    opp = await _owned_opp(client)
    _a, token = await _link(client, opp["id"])
    url = f"{V1}/public/intake/{token}"
    for patch in ({"legal_name": ""}, {"signatory_email": "not-an-email"}, {"confirm_accuracy": False},
                  {"shared_storage_tb": -1}, {"compute_fabric": "TOKEN_RING"}, {"admin": True}):
        assert (await client.post(url, json={**GOOD, **patch})).status_code == 422, patch
    missing = {k: v for k, v in GOOD.items() if k != "registered_address"}
    assert (await client.post(url, json=missing)).status_code == 422
    assert mails == []
    # Still PENDING: nothing was stored.
    assert (await client.get(url)).json()["status"] == "PENDING"


async def test_unknown_revoked_and_expired_links(client, session, mails):
    assert (await client.get(f"{V1}/public/intake/nope")).status_code == 404
    opp = await _owned_opp(client)
    admin, token = await _link(client, opp["id"])
    # Expired -> 410 with a friendly message.
    row = (await session.execute(select(OrderFormIntake))).scalars().one()
    row.expires_at = datetime.now(UTC) - timedelta(days=1)
    await session.commit()
    r = await client.get(f"{V1}/public/intake/{token}")
    assert r.status_code == 410 and "expired" in r.json()["detail"]
    assert (await client.post(f"{V1}/public/intake/{token}", json=GOOD)).status_code == 410
    listed = (await client.get(f"{V1}/intake/opportunity/{opp['id']}")).json()
    assert listed[0]["expired"] is True
    # Revoke -> 404, and it disappears from the list.
    assert (await client.post(f"{V1}/intake/{admin['id']}/revoke")).json()["status"] == "REVOKED"
    assert (await client.get(f"{V1}/public/intake/{token}")).status_code == 404
    assert (await client.get(f"{V1}/intake/opportunity/{opp['id']}")).json() == []


async def test_new_link_revokes_the_one_still_waiting_and_the_link_can_be_copied_again(client, mails, monkeypatch):
    from neocloud.domains.emailsync import oauth

    monkeypatch.setattr(oauth, "encrypt_token", lambda s, t: "enc:" + t)
    monkeypatch.setattr(oauth, "decrypt_token", lambda s, b: b.removeprefix("enc:"))
    opp = await _owned_opp(client)
    _a1, t1 = await _link(client, opp["id"])
    _a2, t2 = await _link(client, opp["id"])
    assert t1 != t2
    assert (await client.get(f"{V1}/public/intake/{t1}")).status_code == 404
    assert (await client.get(f"{V1}/public/intake/{t2}")).status_code == 200
    listed = (await client.get(f"{V1}/intake/opportunity/{opp['id']}")).json()
    assert [x["token"] for x in listed] == [t2]  # the stored (encrypted) copy lets staff copy it again
    assert (await client.post(f"{V1}/intake/opportunity/nope/link")).status_code == 404


async def test_reopen_lets_the_customer_correct_what_they_sent(client, mails):
    opp = await _owned_opp(client)
    admin, token = await _link(client, opp["id"])
    await client.post(f"{V1}/public/intake/{token}", json=GOOD)
    assert (await client.post(f"{V1}/intake/{admin['id']}/reopen")).json()["status"] == "PENDING"
    form = (await client.get(f"{V1}/public/intake/{token}")).json()
    assert form["status"] == "PENDING" and form["prefill"]["signatory_name"] == "Ana Souza"  # starts from the earlier answers
    fixed = {**GOOD, "signatory_name": "Ana Souza Lima"}
    assert (await client.post(f"{V1}/public/intake/{token}", json=fixed)).status_code == 200
    assert len(mails) == 2
    assert (await client.get(f"{V1}/intake/opportunity/{opp['id']}")).json()[0]["data"]["signatory_name"] == "Ana Souza Lima"


def test_recipients_fall_back_to_the_alert_list_without_an_owner_email():
    st = Settings(lead_alert_emails="a@tensorbay.io, b@tensorbay.io")
    assert service.recipients_for(st, "owner@tensorbay.io") == ["owner@tensorbay.io"]
    assert service.recipients_for(st, None) == ["a@tensorbay.io", "b@tensorbay.io"]
    assert service.recipients_for(Settings(lead_alert_emails=""), None) == []


def test_email_is_escaped_and_never_raises(monkeypatch):
    calls = []
    fake = SimpleNamespace(send_email=lambda **kw: calls.append(kw))
    monkeypatch.setattr(service.boto3, "client", lambda *a, **k: fake)
    st = Settings(ses_from_email="crm@tensorbay.io", app_base_url="https://crm.tensorbay.io")
    n = service.SubmittedNotice("opp1", "Deal", "Evil <script>alert(1)</script>\nBcc: x@y.z", "A, B", "a@b.co", "B300", 8)
    service.send_submitted_email(st, n, ["lizi@tensorbay.io"])
    (kw,) = calls
    html_body = kw["Message"]["Body"]["Html"]["Data"]
    assert "<script>" not in html_body and "&lt;script&gt;" in html_body
    assert "\n" not in kw["Message"]["Subject"]["Data"] and "https://crm.tensorbay.io/opportunities/opp1#documents" in html_body
    # SES failure is swallowed (the customer's submission must not fail).
    fake.send_email = lambda **kw: (_ for _ in ()).throw(RuntimeError("ses down"))
    service.send_submitted_email(st, n, ["lizi@tensorbay.io"])
    service.send_submitted_email(Settings(ses_from_email=None), n, ["lizi@tensorbay.io"])  # no sender: skipped


async def test_documents_use_the_customer_intake(client, env, mails):  # noqa: F811
    opp = await _deal(client)
    _a, token = await _link(client, opp["id"])
    await client.post(f"{V1}/public/intake/{token}", json=GOOD)

    _, msa = await _generate(client, opp, doc_type="MSA")
    assert msa["status"] == "GENERATED", msa
    text = _text((await client.get(f"{V1}/documents/{msa['id']}/download")).content)
    assert "FOXGAROO LTDA" in text and "a limited liability company organized under the laws of Brazil" in text
    assert "registration number 12.345.678/0001-90" in text and "Av. Paulista 1000 São Paulo, SP" in text
    assert "represented by Ana Souza, CEO" in text
    assert "☒ NVIDIA Quantum InfiniBand (NDR)" in text and "☐ RoCE v2 Ethernet" in text
    assert "approx. 500 TB usable" in text and "Dedicated internet 10 Gb/s with 20 TB per month" in text
    assert "Customer requirements: Ubuntu 22.04" in text
    assert "Tec Guy, tec@foxgaroo.com, +55 11 5555" in text
    assert "Access from the customer's declared addresses: 203.0.113.0/24" in text
    assert "[Customer note, to be reviewed] Please call first" in text
    assert "to be completed]" not in text.split("registered address")[1][:200]

    # AI drafts get the same data in the deal context (and the instruction to use it).
    env.prompts.clear()
    await _generate(client, opp, doc_type="PROPOSAL")
    system, user = env.prompts[-1]
    assert '"customer_intake"' in user and "Pre-training a 70B model" in user and "ana@foxgaroo.com" in user
    assert "customer_intake" in system
