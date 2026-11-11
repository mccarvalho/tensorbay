"""Sales-role users become lead-eligible reps (SALES / SALES_MANAGER)."""

import pytest
from httpx import AsyncClient

from neocloud.auth.dependencies import CurrentUser, get_current_user
from neocloud.auth.rbac import permissions_for_roles
from neocloud.domains.admin.router import _service
from neocloud.domains.admin.schemas import AdminUser

V1 = "/v1"


def _u(username, email, roles, sub=None, enabled=True, name=None) -> AdminUser:
    return AdminUser(
        username=username, sub=sub or f"sub-{username}", email=email, name=name,
        status="CONFIRMED", enabled=enabled, roles=roles,
    )


class FakeAdmin:
    def __init__(self, users):
        self.users = users

    def list_all_users(self):
        return self.users


@pytest.fixture
def pool():
    """Install a fake Cognito pool; tests mutate ``pool.users`` between syncs."""
    from neocloud.main import app

    fake = FakeAdmin([])
    app.dependency_overrides[_service] = lambda: fake
    yield fake
    app.dependency_overrides.pop(_service, None)


async def _sync(client: AsyncClient) -> dict:
    r = await client.post(f"{V1}/admin/sync-sales-reps")
    assert r.status_code == 200, r.text
    return r.json()


async def _reps(client: AsyncClient) -> dict:
    rows = (await client.get(f"{V1}/economics/reps?limit=500")).json()
    return {r["email"]: r for r in rows}


async def test_sales_and_manager_users_become_lead_eligible_ams(client, pool) -> None:
    pool.users = [
        _u("a", "Ann@Example.com", ["SALES"], name="Ann"),
        _u("b", "bob@example.com", ["SALES_MANAGER"]),
        _u("c", "ops@example.com", ["OPERATIONS"]),
        _u("d", "off@example.com", ["SALES"], enabled=False),
    ]
    assert (await _sync(client))["created"] == 2
    reps = await _reps(client)
    assert set(reps) == {"ann@example.com", "bob@example.com"}
    assert reps["ann@example.com"]["name"] == "Ann"
    assert reps["bob@example.com"]["name"] == "bob"
    assert reps["ann@example.com"]["type"] == "AM"
    assert reps["ann@example.com"]["cognito_sub"] == "sub-a"
    assert all(r["lead_eligible"] for r in reps.values())
    # Idempotent.
    assert await _sync(client) == {"created": 0, "enabled": 0, "disabled": 0}


async def test_synced_users_receive_routed_leads(client, pool) -> None:
    pool.users = [_u("a", "ann@example.com", ["SALES"], name="Ann")]
    await _sync(client)
    res = (await client.post(f"{V1}/leads/ingest", json={
        "submission_id": "s1", "name": "L", "email": "l@x.com", "region": "Europe",
    }, headers={"Authorization": "Bearer test-ingest-token"})).json()
    assert res["assigned_to"] == "Ann"


async def test_losing_the_role_or_being_disabled_stops_lead_routing(client, pool) -> None:
    pool.users = [_u("a", "ann@example.com", ["SALES"], name="Ann")]
    await _sync(client)
    pool.users = [_u("a", "ann@example.com", ["OPERATIONS"], name="Ann")]
    assert (await _sync(client))["disabled"] == 1
    assert (await _reps(client))["ann@example.com"]["lead_eligible"] is False
    # Role returns -> same rep is re-enabled, not duplicated.
    pool.users = [_u("a", "ann@example.com", ["SALES"], name="Ann")]
    assert (await _sync(client))["enabled"] == 1
    assert len(await _reps(client)) == 1
    # Disabled in Cognito.
    pool.users = [_u("a", "ann@example.com", ["SALES"], enabled=False)]
    await _sync(client)
    assert (await _reps(client))["ann@example.com"]["lead_eligible"] is False
    # Deleted from Cognito altogether.
    pool.users = [_u("a", "ann@example.com", ["SALES"])]
    await _sync(client)
    pool.users = []
    await _sync(client)
    assert (await _reps(client))["ann@example.com"]["lead_eligible"] is False


async def test_existing_rep_is_linked_not_duplicated_and_keeps_its_settings(client, pool) -> None:
    made = (await client.post(f"{V1}/economics/reps", json={
        "name": "Existing AE", "type": "AE", "email": "eve@example.com", "regions": "EMEA",
    })).json()
    assert made["lead_eligible"] is False  # AEs default to not receiving leads
    pool.users = [_u("e", "eve@example.com", ["SALES"])]
    assert (await _sync(client)) == {"created": 0, "enabled": 1, "disabled": 0}
    rep = (await _reps(client))["eve@example.com"]
    assert rep["id"] == made["id"] and rep["type"] == "AE" and rep["regions"] == "EMEA"
    assert rep["lead_eligible"] and rep["cognito_sub"] == "sub-e"


async def test_native_and_google_twins_count_as_one_person(client, pool) -> None:
    pool.users = [
        _u("native-1", "lizi@example.com", ["SALES"], sub="s-native"),
        _u("Google_1", "lizi@example.com", ["SALES"], sub="s-google"),
    ]
    assert (await _sync(client))["created"] == 1
    # One twin loses the role while the other keeps it: still eligible.
    pool.users = [
        _u("native-1", "lizi@example.com", ["OPERATIONS"], sub="s-native"),
        _u("Google_1", "lizi@example.com", ["SALES"], sub="s-google"),
    ]
    await _sync(client)
    assert (await _reps(client))["lizi@example.com"]["lead_eligible"] is True


async def test_rep_never_linked_to_a_user_is_left_alone(client, pool) -> None:
    await client.post(f"{V1}/economics/reps", json={"name": "Offline AM", "type": "AM"})
    pool.users = []
    assert (await _sync(client))["disabled"] == 0
    rows = (await client.get(f"{V1}/economics/reps")).json()
    assert rows[0]["lead_eligible"] is True


async def test_am_sees_leads_when_logged_in_with_a_different_sub_but_same_email(client, pool) -> None:
    from neocloud.main import app

    pool.users = [_u("a", "ann@example.com", ["SALES"], sub="sub-native", name="Ann")]
    await _sync(client)
    await client.post(f"{V1}/leads/ingest", json={
        "submission_id": "s1", "name": "L", "email": "l@x.com"},
        headers={"Authorization": "Bearer test-ingest-token"})
    roles = ["SALES"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="sub-google-twin", email="Ann@Example.com", roles=roles,
        permissions=permissions_for_roles(roles),
    )
    try:
        assert len((await client.get(f"{V1}/leads")).json()) == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_only_user_admins_can_run_the_sync(client, pool) -> None:
    from neocloud.main import app

    roles = ["SALES_MANAGER"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="m", email=None, roles=roles, permissions=permissions_for_roles(roles)
    )
    try:
        assert (await client.post(f"{V1}/admin/sync-sales-reps")).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
