from httpx import AsyncClient

V1 = "/v1"


async def test_supplier_crud_and_contact(client: AsyncClient) -> None:
    create = await client.post(
        f"{V1}/suppliers",
        json={
            "name": "Oracle",
            "legal_name": "Oracle Corporation",
            "tier": "CLOUD",
            "status": "ACTIVE",
            "country": "US",
        },
    )
    assert create.status_code == 201, create.text
    supplier = create.json()
    assert supplier["name"] == "Oracle"
    assert supplier["tier"] == "CLOUD"
    assert supplier["id"]
    supplier_id = supplier["id"]

    # List + search
    listed = await client.get(f"{V1}/suppliers", params={"q": "ora"})
    assert listed.status_code == 200
    assert any(s["id"] == supplier_id for s in listed.json())

    # Contact
    contact = await client.post(
        f"{V1}/suppliers/{supplier_id}/contacts",
        json={"name": "Jane Doe", "role": "Account Exec", "email": "jane@oracle.com"},
    )
    assert contact.status_code == 201, contact.text
    assert contact.json()["supplier_id"] == supplier_id


async def test_incoming_capacity_links_supplier_and_status(
    client: AsyncClient,
) -> None:
    sup = await client.post(
        f"{V1}/suppliers", json={"name": "Oracle", "tier": "CLOUD"}
    )
    supplier_id = sup.json()["id"]

    # 1200 B200 being negotiated with Oracle, no SKU required.
    inc = await client.post(
        f"{V1}/capacity/incoming",
        json={
            "gpu_model": "B200",
            "quantity": 1200,
            "supplier_id": supplier_id,
            "status": "NEGOTIATING",
            "unit_price": "32000.00",
            "currency": "USD",
            "expected_delivery": "2026-12-01",
        },
    )
    assert inc.status_code == 201, inc.text
    body = inc.json()
    assert body["supplier_id"] == supplier_id
    assert body["status"] == "NEGOTIATING"
    assert body["quantity"] == 1200
    assert body["expected_delivery"] == "2026-12-01"
    inc_id = body["id"]

    # Promote to ORDERED and add official delivery date.
    patch = await client.patch(
        f"{V1}/capacity/incoming/{inc_id}",
        json={"status": "DELIVERED", "actual_delivery": "2026-12-05"},
    )
    assert patch.status_code == 200, patch.text
    assert patch.json()["status"] == "DELIVERED"
    assert patch.json()["actual_delivery"] == "2026-12-05"
