import pytest
from httpx import AsyncClient

from neocloud.auth.dependencies import CurrentUser, get_current_user
from neocloud.auth.rbac import permissions_for_roles
from neocloud.domains.leads.parsing import (
    clean,
    extract_region_from_message,
    parse_gpu_count,
    region_matches,
    split_region,
)

V1 = "/v1"
AUTH = {"Authorization": "Bearer test-ingest-token"}


# --------------------------------------------------------------------------- #
# Parsing helpers
# --------------------------------------------------------------------------- #
def test_clean_treats_markers_as_empty() -> None:
    for marker in (None, "", "  ", "—", "-", "N/A", "none", "null"):
        assert clean(marker) is None
    assert clean("  Syaala ") == "Syaala"


def test_parse_gpu_count() -> None:
    assert parse_gpu_count("8") == 8
    assert parse_gpu_count("8 GPUs") == 8
    assert parse_gpu_count("1,024") == 1024
    assert parse_gpu_count(16) == 16
    assert parse_gpu_count("—") is None
    assert parse_gpu_count("0") is None
    assert parse_gpu_count("many") is None


def test_split_region() -> None:
    assert split_region("North America · United States") == ("North America", "United States")
    assert split_region("LATAM") == ("LATAM", None)
    assert split_region("—") == (None, None)


def test_extract_region_from_message_matches_original_email() -> None:
    msg = "Region for your quote: North America · United States\n\nModular data center suppliers."
    region, country, rest = extract_region_from_message(msg)
    assert (region, country) == ("North America", "United States")
    assert rest == "Modular data center suppliers."
    # No region line -> untouched.
    assert extract_region_from_message("just text") == (None, None, "just text")


def test_region_matches_is_not_fooled_by_short_codes() -> None:
    assert region_matches("North America, LATAM", "North America", "United States")
    assert region_matches("latam", "LATAM", None)
    assert region_matches("United States", None, "United States")
    # "us" must not match inside "Australia".
    assert not region_matches("us", "APAC", "Australia")
    assert region_matches("us", None, "US")
    assert not region_matches(None, "North America", None)
    assert not region_matches("LATAM", None, None)


# --------------------------------------------------------------------------- #
# Ingest: auth, parsing, idempotency
# --------------------------------------------------------------------------- #
SAMPLE = {
    "submission_id": "sub-001",
    "name": "Sujay Namburi",
    "email": "Sujay@syaala.com",
    "company": "Syaala",
    "sku_of_interest": "—",
    "gpu_count": "—",
    "pricing_model_or_term": "—",
    "site_language": "en",
    "message": "Region for your quote: North America · United States\n\nModular data center suppliers.",
}


async def test_ingest_requires_valid_token(client: AsyncClient) -> None:
    r = await client.post(f"{V1}/leads/ingest", json=SAMPLE)
    assert r.status_code == 401
    r = await client.post(
        f"{V1}/leads/ingest", json=SAMPLE, headers={"Authorization": "Bearer nope"}
    )
    assert r.status_code == 401
    r = await client.post(
        f"{V1}/leads/ingest", json=SAMPLE, headers={"Authorization": "Basic test-ingest-token"}
    )
    assert r.status_code == 401


async def test_ingest_original_email_payload(client: AsyncClient) -> None:
    r = await client.post(f"{V1}/leads/ingest", json=SAMPLE, headers=AUTH)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "created"
    assert body["needs_review"] is False  # region recovered from the message

    lead = (await client.get(f"{V1}/leads/{body['id']}")).json()
    assert lead["email"] == "sujay@syaala.com"  # normalised to lowercase
    assert lead["company"] == "Syaala"
    assert lead["sku_of_interest"] is None  # "—" -> null
    assert lead["gpu_count"] is None
    assert lead["pricing_model_or_term"] is None
    assert lead["region"] == "North America"
    assert lead["country"] == "United States"
    assert lead["message"] == "Modular data center suppliers."
    assert lead["status"] == "NEW"


async def test_ingest_structured_fields_and_extras(client: AsyncClient) -> None:
    payload = {
        "submission_id": "sub-002",
        "name": "Ana",
        "email": "ana@example.com",
        "gpu_count": 64,
        "sku_of_interest": "H100",
        "region": "LATAM",
        "country": "Brazil",
        "utm_campaign": "launch",  # unknown extra field is accepted
    }
    r = await client.post(f"{V1}/leads/ingest", json=payload, headers=AUTH)
    assert r.status_code == 201, r.text
    lead = (await client.get(f"{V1}/leads/{r.json()['id']}")).json()
    assert lead["gpu_count"] == 64
    assert lead["sku_of_interest"] == "H100"
    assert (lead["region"], lead["country"]) == ("LATAM", "Brazil")


async def test_ingest_without_region_is_flagged_for_review(client: AsyncClient) -> None:
    r = await client.post(
        f"{V1}/leads/ingest",
        json={"submission_id": "sub-003", "name": "No Region", "email": "nr@example.com"},
        headers=AUTH,
    )
    assert r.status_code == 201
    assert r.json()["needs_review"] is True


async def test_ingest_is_idempotent_on_submission_id(client: AsyncClient) -> None:
    first = await client.post(f"{V1}/leads/ingest", json=SAMPLE, headers=AUTH)
    again = await client.post(f"{V1}/leads/ingest", json=SAMPLE, headers=AUTH)
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["status"] == "duplicate"
    assert again.json()["id"] == first.json()["id"]
    leads = (await client.get(f"{V1}/leads")).json()
    assert len(leads) == 1


async def test_ingest_validation_errors(client: AsyncClient) -> None:
    r = await client.post(
        f"{V1}/leads/ingest",
        json={"submission_id": "x", "name": "A", "email": "not-an-email"},
        headers=AUTH,
    )
    assert r.status_code == 422
    r = await client.post(f"{V1}/leads/ingest", json={"name": "A"}, headers=AUTH)
    assert r.status_code == 422


async def test_ingest_rejects_oversized_payload(client: AsyncClient) -> None:
    payload = {
        "submission_id": "big-1",
        "name": "Big",
        "email": "big@example.com",
        "region": "LATAM",
        "junk": "x" * 25_000,
    }
    r = await client.post(f"{V1}/leads/ingest", json=payload, headers=AUTH)
    assert r.status_code == 413


async def test_repeat_email_links_to_open_lead(client: AsyncClient) -> None:
    a = await client.post(
        f"{V1}/leads/ingest",
        json={"submission_id": "r-1", "name": "Rep", "email": "same@example.com", "region": "EMEA"},
        headers=AUTH,
    )
    b = await client.post(
        f"{V1}/leads/ingest",
        json={"submission_id": "r-2", "name": "Rep", "email": "SAME@example.com", "region": "EMEA"},
        headers=AUTH,
    )
    second = (await client.get(f"{V1}/leads/{b.json()['id']}")).json()
    assert second["duplicate_of_id"] == a.json()["id"]


# --------------------------------------------------------------------------- #
# Routing to Account Managers
# --------------------------------------------------------------------------- #
async def _am(client: AsyncClient, name: str, regions: str | None, email: str | None = None):
    body: dict = {"name": name, "type": "AM"}
    if regions is not None:
        body["regions"] = regions
    if email:
        body["email"] = email
    return (await client.post(f"{V1}/economics/reps", json=body)).json()


async def _ingest(client: AsyncClient, sid: str, region: str | None, country: str | None = None):
    body: dict = {"submission_id": sid, "name": f"Lead {sid}", "email": f"{sid}@example.com"}
    if region:
        body["region"] = region
    if country:
        body["country"] = country
    return (await client.post(f"{V1}/leads/ingest", json=body, headers=AUTH)).json()


async def test_routing_prefers_region_match_then_catch_all(client: AsyncClient) -> None:
    na = await _am(client, "Nora NA", "North America")
    latam = await _am(client, "Luis LATAM", "LATAM, Brazil")
    catch_all = await _am(client, "Cato All", None)

    r1 = await _ingest(client, "n1", "North America", "United States")
    r2 = await _ingest(client, "l1", "LATAM", "Brazil")
    r3 = await _ingest(client, "e1", "Europe")
    assert r1["assigned_to"] == na["name"]
    assert r2["assigned_to"] == latam["name"]
    assert r3["assigned_to"] == catch_all["name"]  # no AM covers Europe


async def test_routing_balances_load_within_a_region(client: AsyncClient) -> None:
    a = await _am(client, "Alpha", "North America")
    b = await _am(client, "Bravo", "North America")
    seen = [(await _ingest(client, f"b{i}", "North America"))["assigned_to"] for i in range(4)]
    # Two AMs cover the region: leads alternate rather than piling on one.
    assert seen.count(a["name"]) == 2
    assert seen.count(b["name"]) == 2


async def test_routing_ignores_inactive_ams_and_non_ams(client: AsyncClient) -> None:
    await client.post(f"{V1}/economics/reps", json={"name": "An AE", "type": "AE", "regions": "LATAM"})
    inactive = await _am(client, "Gone", "LATAM")
    await client.patch(f"{V1}/economics/reps/{inactive['id']}", json={"status": "INACTIVE"})
    res = await _ingest(client, "z1", "LATAM")
    assert res["assigned_to"] is None  # nobody eligible -> unassigned, not lost
    lead = (await client.get(f"{V1}/leads/{res['id']}")).json()
    assert lead["assigned_rep_id"] is None


# --------------------------------------------------------------------------- #
# Working a lead: update / disqualify / convert
# --------------------------------------------------------------------------- #
async def test_update_and_disqualify(client: AsyncClient) -> None:
    lead = await _ingest(client, "u1", "LATAM")
    upd = await client.patch(f"{V1}/leads/{lead['id']}", json={"status": "CONTACTED", "notes": "called"})
    assert upd.status_code == 200
    assert upd.json()["status"] == "CONTACTED"

    # CONVERTED / DISQUALIFIED can't be set through the generic patch.
    assert (await client.patch(f"{V1}/leads/{lead['id']}", json={"status": "CONVERTED"})).status_code == 422
    assert (await client.patch(f"{V1}/leads/{lead['id']}", json={"status": "DISQUALIFIED"})).status_code == 422

    dq = await client.post(f"{V1}/leads/{lead['id']}/disqualify", json={"reason": "Not a buyer"})
    assert dq.status_code == 200
    assert dq.json()["status"] == "DISQUALIFIED"
    assert dq.json()["disqualified_reason"] == "Not a buyer"


async def test_convert_creates_customer_contact_activity(client: AsyncClient) -> None:
    am = await _am(client, "Conv AM", None, "conv@tensorbay.io")
    r = await client.post(f"{V1}/leads/ingest", json=SAMPLE, headers=AUTH)
    lead_id = r.json()["id"]

    conv = await client.post(f"{V1}/leads/{lead_id}/convert", json={})
    assert conv.status_code == 200, conv.text
    out = conv.json()
    assert out["customer_created"] is True
    assert out["opportunity_id"] is None
    assert out["lead"]["status"] == "CONVERTED"
    assert out["lead"]["converted_customer_id"] == out["customer_id"]

    customer = (await client.get(f"{V1}/customers/{out['customer_id']}")).json()
    assert customer["legal_name"] == "Syaala"
    assert customer["status"] == "PROSPECT"
    assert customer["account_owner"] == am["name"]

    contacts = (await client.get(f"{V1}/customers/{out['customer_id']}/contacts")).json()
    assert [c["email"] for c in contacts] == ["sujay@syaala.com"]
    acts = (await client.get(f"{V1}/customers/{out['customer_id']}/activities")).json()
    assert acts[0]["type"] == "EMAIL"
    assert "Modular data center suppliers." in acts[0]["notes"]

    # Converting twice is rejected.
    assert (await client.post(f"{V1}/leads/{lead_id}/convert", json={})).status_code == 409


async def test_convert_reuses_existing_customer(client: AsyncClient) -> None:
    a = await client.post(f"{V1}/leads/ingest", json=SAMPLE, headers=AUTH)
    second = {**SAMPLE, "submission_id": "sub-other", "name": "Colleague", "email": "colleague@syaala.com"}
    b = await client.post(f"{V1}/leads/ingest", json=second, headers=AUTH)
    ca = (await client.post(f"{V1}/leads/{a.json()['id']}/convert", json={})).json()
    cb = (await client.post(f"{V1}/leads/{b.json()['id']}/convert", json={})).json()
    assert cb["customer_id"] == ca["customer_id"]
    assert cb["customer_created"] is False
    contacts = (await client.get(f"{V1}/customers/{ca['customer_id']}/contacts")).json()
    assert len(contacts) == 2


async def test_convert_with_opportunity(client: AsyncClient) -> None:
    r = await client.post(
        f"{V1}/leads/ingest",
        json={
            "submission_id": "o-1",
            "name": "Opp Person",
            "email": "opp@example.com",
            "company": "OppCo",
            "region": "LATAM",
            "sku_of_interest": "H100",
            "gpu_count": 32,
        },
        headers=AUTH,
    )
    lead_id = r.json()["id"]
    # Missing term/model/MRR -> told exactly what's needed.
    bad = await client.post(f"{V1}/leads/{lead_id}/convert", json={"create_opportunity": True})
    assert bad.status_code == 422
    assert "duration_months" in bad.text and "expected_mrr" in bad.text

    ok = await client.post(
        f"{V1}/leads/{lead_id}/convert",
        json={
            "create_opportunity": True,
            "duration_months": 12,
            "commercial_model": "RESERVED",
            "expected_mrr": "50000.00",
        },
    )
    assert ok.status_code == 200, ok.text
    opp_id = ok.json()["opportunity_id"]
    assert opp_id
    opp = (await client.get(f"{V1}/sales/opportunities/{opp_id}")).json()
    assert opp["gpu_model"] == "H100"  # defaulted from the lead's SKU
    assert opp["quantity"] == 32  # defaulted from the lead's GPU count
    assert opp["sales_stage"] == "PROSPECTING"


# --------------------------------------------------------------------------- #
# Access control: an Account Manager only sees their own leads
# --------------------------------------------------------------------------- #
@pytest.fixture
def as_am():
    """Run requests as a plain SALES user linked to a given cognito sub."""
    from neocloud.main import app

    def _set(sub: str) -> None:
        roles = ["SALES"]
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            subject=sub,
            email="am@example.com",
            roles=roles,
            permissions=permissions_for_roles(roles),
        )

    yield _set
    app.dependency_overrides.pop(get_current_user, None)


async def test_account_manager_only_sees_own_leads(client: AsyncClient, as_am) -> None:
    mine = await client.post(
        f"{V1}/economics/reps",
        json={"name": "Mine", "type": "AM", "regions": "LATAM", "cognito_sub": "sub-mine"},
    )
    await client.post(
        f"{V1}/economics/reps",
        json={"name": "Theirs", "type": "AM", "regions": "EMEA", "cognito_sub": "sub-theirs"},
    )
    my_lead = await _ingest(client, "m1", "LATAM")
    other_lead = await _ingest(client, "t1", "EMEA")
    assert my_lead["assigned_to"] == "Mine"

    as_am("sub-mine")
    listed = (await client.get(f"{V1}/leads")).json()
    assert [lead["id"] for lead in listed] == [my_lead["id"]]
    assert (await client.get(f"{V1}/leads/{my_lead['id']}")).status_code == 200
    assert (await client.get(f"{V1}/leads/{other_lead['id']}")).status_code == 403
    # Can work own lead, but can't reassign it or touch someone else's.
    assert (
        await client.patch(f"{V1}/leads/{my_lead['id']}", json={"status": "CONTACTED"})
    ).status_code == 200
    assert (
        await client.patch(f"{V1}/leads/{my_lead['id']}", json={"assigned_rep_id": mine.json()["id"]})
    ).status_code == 403
    assert (
        await client.post(f"{V1}/leads/{other_lead['id']}/disqualify", json={"reason": "x"})
    ).status_code == 403


async def test_user_without_lead_permission_is_denied(client: AsyncClient) -> None:
    from neocloud.main import app

    roles = ["FINANCE"]  # finance has no lead.* permission
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="fin", email=None, roles=roles, permissions=permissions_for_roles(roles)
    )
    try:
        assert (await client.get(f"{V1}/leads")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
