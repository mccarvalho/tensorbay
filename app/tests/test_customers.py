"""Customer CRUD round-trip (auth disabled -> stub SUPER_ADMIN user)."""

from httpx import AsyncClient

V1 = "/v1"


async def test_create_then_get_customer(client: AsyncClient) -> None:
    payload = {
        "legal_name": "Acme GPU Labs Ltda",
        "trading_name": "Acme GPU",
        "tax_id": "12.345.678/0001-90",
        "country": "BR",
        "currency": "BRL",
        "status": "ACTIVE",
        "credit_status": "GOOD",
        "account_owner": "sales@neocloud",
        "industry": "AI",
    }

    create = await client.post(f"{V1}/customers", json=payload)
    assert create.status_code == 201, create.text
    created = create.json()
    assert created["legal_name"] == "Acme GPU Labs Ltda"
    assert created["status"] == "ACTIVE"
    assert created["id"]
    # Audit mixin populated server-side.
    assert created["created_at"]
    customer_id = created["id"]

    got = await client.get(f"{V1}/customers/{customer_id}")
    assert got.status_code == 200, got.text
    fetched = got.json()
    assert fetched["id"] == customer_id
    assert fetched["legal_name"] == "Acme GPU Labs Ltda"
    assert fetched["trading_name"] == "Acme GPU"


async def test_get_missing_customer_404(client: AsyncClient) -> None:
    resp = await client.get(f"{V1}/customers/does-not-exist")
    assert resp.status_code == 404


async def _customer(client: AsyncClient) -> str:
    r = await client.post(f"{V1}/customers", json={"legal_name": "CRM Co", "status": "PROSPECT"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_contact_role_can_be_set_edited_and_deleted(client: AsyncClient) -> None:
    cid = await _customer(client)
    made = await client.post(
        f"{V1}/customers/{cid}/contacts",
        json={"type": "COMMERCIAL", "name": "Joe Deng", "role": "CTO", "email": "joe@akash.network"},
    )
    assert made.status_code == 201, made.text
    contact = made.json()
    assert contact["role"] == "CTO" and contact["phone"] is None

    upd = await client.patch(
        f"{V1}/customers/{cid}/contacts/{contact['id']}", json={"role": "VP Engineering"}
    )
    assert upd.status_code == 200 and upd.json()["role"] == "VP Engineering"
    assert upd.json()["name"] == "Joe Deng"  # untouched

    # Role can be cleared again.
    cleared = await client.patch(f"{V1}/customers/{cid}/contacts/{contact['id']}", json={"role": None})
    assert cleared.json()["role"] is None

    assert (await client.delete(f"{V1}/customers/{cid}/contacts/{contact['id']}")).status_code == 204
    assert (await client.get(f"{V1}/customers/{cid}/contacts")).json() == []


async def test_deleting_a_contact_keeps_its_activities(client: AsyncClient) -> None:
    cid = await _customer(client)
    contact = (await client.post(
        f"{V1}/customers/{cid}/contacts", json={"type": "TECHNICAL", "name": "Ann"}
    )).json()
    act = await client.post(
        f"{V1}/customers/{cid}/activities",
        json={"type": "CALL", "subject": "Intro", "contact_id": contact["id"]},
    )
    assert act.status_code == 201, act.text
    assert (await client.delete(f"{V1}/customers/{cid}/contacts/{contact['id']}")).status_code == 204
    remaining = (await client.get(f"{V1}/customers/{cid}/activities")).json()
    assert len(remaining) == 1 and remaining[0]["subject"] == "Intro"


async def test_activity_supports_slack_and_a_backdated_time(client: AsyncClient) -> None:
    cid = await _customer(client)
    r = await client.post(
        f"{V1}/customers/{cid}/activities",
        json={"type": "SLACK", "subject": "Pricing thread", "occurred_at": "2026-11-05T14:30:00Z"},
    )
    assert r.status_code == 201, r.text
    assert r.json()["type"] == "SLACK"
    assert r.json()["occurred_at"].startswith("2026-11-05T14:30")

    # Editing the date afterwards fixes a wrongly-logged entry.
    fixed = await client.patch(
        f"{V1}/customers/{cid}/activities/{r.json()['id']}",
        json={"occurred_at": "2026-11-04T09:00:00Z"},
    )
    assert fixed.status_code == 200 and fixed.json()["occurred_at"].startswith("2026-11-04T09:00")

    # Timeline is ordered by when it happened, not when it was typed in.
    await client.post(f"{V1}/customers/{cid}/activities", json={"type": "NOTE", "subject": "Now"})
    subjects = [a["subject"] for a in (await client.get(f"{V1}/customers/{cid}/activities")).json()]
    assert subjects == ["Now", "Pricing thread"]

    assert (await client.post(
        f"{V1}/customers/{cid}/activities", json={"type": "TELEGRAM", "subject": "x"}
    )).status_code == 422
