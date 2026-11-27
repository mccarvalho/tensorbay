"""Orders are in whole 8-GPU servers; under 32 servers (256 GPUs) an administrator must approve."""
from httpx import AsyncClient

from neocloud.auth.dependencies import CurrentUser, get_current_user
from neocloud.auth.rbac import ROLE_PERMISSIONS, Role
from neocloud.main import app

V1 = "/v1"


def _as(role: Role):
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject=f"{role}-user", email=f"{role.lower()}@tensorbay.io", roles=[role], permissions=set(ROLE_PERMISSIONS[role]),
    )


async def _body(client: AsyncClient, qty: int, **extra) -> dict:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": f"Min {qty}", "status": "PROSPECT"})).json()["id"]
    return {"customer_id": cid, "gpu_model": "B300", "quantity": qty, "duration_months": 36,
            "commercial_model": "GPU_MONTHLY", "expected_mrr": "100000", "probability": 10, **extra}


async def test_quantity_must_be_a_multiple_of_8(client: AsyncClient):
    r = await client.post(f"{V1}/sales/opportunities", json=await _body(client, 260))
    assert r.status_code == 422 and "multiple of 8" in r.text
    ok = await client.post(f"{V1}/sales/opportunities", json=await _body(client, 264))
    assert ok.status_code == 201
    r = await client.patch(f"{V1}/sales/opportunities/{ok.json()['id']}", json={"quantity": 270})
    assert r.status_code == 422


async def test_at_or_above_32_servers_needs_no_approval(client: AsyncClient):
    opp = (await client.post(f"{V1}/sales/opportunities", json=await _body(client, 256))).json()
    assert opp["min_order_status"] is None


async def test_below_minimum_waits_for_an_admin_and_cannot_pass_the_proposal(client: AsyncClient):
    _as(Role.SALES)
    try:
        r = await client.post(f"{V1}/sales/opportunities", json=await _body(client, 248))
        assert r.status_code == 201 and r.json()["min_order_status"] == "PENDING"
        opp = r.json()
        # Early stages are fine; commitment stages and documents are blocked.
        assert (await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "PROPOSAL_SENT"})).status_code == 200
        blocked = await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "KYC_SCREENING"})
        assert blocked.status_code == 422 and "administrator must approve" in blocked.text
        doc = await client.post(f"{V1}/documents/generate-for-opportunity", json={"opportunity_id": opp["id"], "doc_type": "MSA"})
        assert doc.status_code == 422 and "waits for an administrator" in doc.text
        # Sales cannot approve it.
        assert (await client.post(f"{V1}/sales/opportunities/{opp['id']}/approve-minimum")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    ok = await client.post(f"{V1}/sales/opportunities/{opp['id']}/approve-minimum")
    assert ok.status_code == 200 and ok.json()["min_order_status"] == "APPROVED" and ok.json()["min_order_approved_by"]
    moved = await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "KYC_SCREENING"})
    assert moved.status_code == 200


async def test_an_admin_saving_a_small_order_approves_it_and_a_size_change_asks_again(client: AsyncClient):
    opp = (await client.post(f"{V1}/sales/opportunities", json=await _body(client, 64))).json()
    assert opp["min_order_status"] == "APPROVED"  # the test user is an administrator
    big = (await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"quantity": 512})).json()
    assert big["min_order_status"] is None and big["min_order_approved_by"] is None
    _as(Role.SALES)
    try:
        small = (await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"quantity": 128})).json()
        assert small["min_order_status"] == "PENDING"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert (await client.post(f"{V1}/sales/opportunities/{big['id']}/approve-minimum")).status_code == 200
