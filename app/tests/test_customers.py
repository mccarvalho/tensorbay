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
