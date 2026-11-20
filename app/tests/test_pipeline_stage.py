"""The pipeline board moves a deal by PATCHing only its sales_stage."""

from httpx import AsyncClient
from sqlalchemy import select

from neocloud.audit.service import AuditEntry as AuditLog

V1 = "/v1"


async def _opp(client: AsyncClient) -> dict:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": "Board Co", "status": "PROSPECT"})).json()["id"]
    r = await client.post(
        f"{V1}/sales/opportunities",
        json={
            "customer_id": cid, "gpu_model": "H200", "quantity": 16, "duration_months": 12,
            "commercial_model": "GPU_MONTHLY", "expected_mrr": "50000", "probability": 40,
            "account_owner": "Lizi",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_stage_only_patch_moves_the_deal_and_leaves_everything_else(client: AsyncClient) -> None:
    opp = await _opp(client)
    assert opp["sales_stage"] == "PROSPECTING"
    for stage in ("QUALIFICATION", "PROPOSAL", "NEGOTIATION", "WON", "NEGOTIATION", "LOST"):
        r = await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": stage})
        assert r.status_code == 200, r.text
        moved = r.json()
        assert moved["sales_stage"] == stage
        for k in ("quantity", "expected_mrr", "probability", "account_owner", "gpu_model", "customer_id"):
            assert moved[k] == opp[k], k
    listed = (await client.get(f"{V1}/sales/opportunities")).json()
    assert [o["sales_stage"] for o in listed if o["id"] == opp["id"]] == ["LOST"]


async def test_unknown_stage_is_rejected_and_nothing_changes(client: AsyncClient) -> None:
    opp = await _opp(client)
    r = await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "DONE"})
    assert r.status_code == 422
    assert (await client.get(f"{V1}/sales/opportunities/{opp['id']}")).json()["sales_stage"] == "PROSPECTING"
    assert (await client.patch(f"{V1}/sales/opportunities/nope", json={"sales_stage": "WON"})).status_code == 404


async def test_each_move_is_audited(client: AsyncClient, session) -> None:
    opp = await _opp(client)
    await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "PROPOSAL"})
    rows = (
        await session.execute(
            select(AuditLog).where(AuditLog.entity_id == opp["id"], AuditLog.action == "update")
        )
    ).scalars().all()
    assert len(rows) == 1 and "PROPOSAL" in str(rows[0].new_value)


async def test_read_only_users_cannot_move_deals(client: AsyncClient) -> None:
    from neocloud.auth.dependencies import CurrentUser, get_current_user
    from neocloud.auth.rbac import permissions_for_roles
    from neocloud.main import app

    opp = await _opp(client)
    roles = ["EXECUTIVE"]  # can read customers/pipeline, cannot write
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="exec", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        assert (await client.get(f"{V1}/sales/opportunities")).status_code == 200
        r = await client.patch(f"{V1}/sales/opportunities/{opp['id']}", json={"sales_stage": "WON"})
        assert r.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
