"""Supply orders: register a GPU purchase by totals + delivery lots + forecast.

Scenario from the signed Positivo proposal (Request 7995995): 64 Supermicro
HGX B300 servers x 8 GPUs = 512 GPUs at US$ 806,101.73 per server, assembled in
Manaus, deployed at Ascenty SP, first lot expected 30 Jan.
"""

from decimal import Decimal

from httpx import AsyncClient

V1 = "/v1"
POSITIVO = {
    "reference": "Positivo Request 7995995",
    "supplier_quote": "SMC 8601671539",
    "gpu_model": "B300",
    "server_model": "Supermicro SYS-822GS-NB3RT (HGX B300 NVL8)",
    "gpus_per_server": 8,
    "servers": 64,
    "unit_price_per_server": "806101.73",
    "currency": "USD",
    "payment_terms": "40% on order / 60% on invoicing in Manaus",
    "assembly_site": "Positivo Tecnologia Manaus (PPB)",
    "destination_site": "Ascenty SP",
    "tax_regime": "REDATA",
    "delivery_window": "6-13 months",
}


async def _supplier(client: AsyncClient) -> str:
    r = await client.post(f"{V1}/suppliers", json={"name": "Positivo Servers and Solutions"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_whole_order_registered_by_totals_in_one_call(client: AsyncClient) -> None:
    sup = await _supplier(client)
    r = await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "supplier_id": sup})
    assert r.status_code == 201, r.text
    o = r.json()
    assert o["gpus_total"] == 512
    assert Decimal(o["total_value"]) == Decimal("51590510.72")  # 64 x 806,101.73 (rounded price)
    # The proposal's exact total can be recorded instead.
    exact = (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "reference": "exact", "total_value": "51590510.51"})).json()
    assert Decimal(exact["total_value"]) == Decimal("51590510.51")
    kept = (await client.patch(f"{V1}/capacity/orders/{exact['id']}", json={"notes": "signed"})).json()
    assert Decimal(kept["total_value"]) == Decimal("51590510.51")  # unrelated edit keeps it
    await client.delete(f"{V1}/capacity/orders/{exact['id']}")
    # No lots given -> one unscheduled lot holding everything.
    assert len(o["lots"]) == 1 and o["lots"][0]["quantity"] == 512 and o["lots"][0]["servers"] == 64
    assert o["unscheduled_gpus"] == 512 and o["unallocated_gpus"] == 0
    # The lot is ordinary incoming capacity: the capacity check sees it.
    chk = (await client.get(f"{V1}/capacity/check", params={"gpu_model": "B300", "quantity": 256})).json()
    assert chk["incoming"] == 512 and chk["status"] == "PARTIALLY_AVAILABLE"
    inc = (await client.get(f"{V1}/capacity/incoming")).json()[0]
    assert inc["purchase_order"] == "Positivo Request 7995995" and inc["supplier_id"] == sup
    assert Decimal(inc["unit_price"]) == Decimal("100762.72")  # per GPU
    assert inc["order_id"] == o["id"]


async def test_lots_in_servers_and_limits(client: AsyncClient) -> None:
    o = (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "lots": [
        {"label": "Lote 1", "servers": 16, "expected_delivery": "2027-01-30"},
    ]})).json()
    assert [(lt["lot_label"], lt["quantity"]) for lt in o["lots"]] == [("Lote 1", 128)]
    assert o["unallocated_gpus"] == 384 and o["next_delivery"] == "2027-01-30"
    url = f"{V1}/capacity/orders/{o['id']}/lots"
    assert (await client.post(url, json={"servers": 48})).status_code == 201
    # Over the contracted total is refused.
    over = await client.post(url, json={"servers": 1})
    assert over.status_code == 409 and "512" in over.json()["detail"]
    assert (await client.post(url, json={"servers": 2, "quantity": 99})).status_code == 422
    assert (await client.post(url, json={})).status_code == 422
    # Shrinking the order below its lots is refused too.
    assert (await client.patch(f"{V1}/capacity/orders/{o['id']}", json={"servers": 60})).status_code == 409


async def test_delivery_updates_status_and_protects_history(client: AsyncClient) -> None:
    o = (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "lots": [
        {"label": "Lote 1", "servers": 16, "expected_delivery": "2027-01-30"},
        {"label": "Lote 2", "servers": 48},
    ]})).json()
    lot1 = o["lots"][0]["id"]
    r = (await client.patch(f"{V1}/capacity/orders/{o['id']}/lots/{lot1}", json={"actual_delivery": "2027-02-02"})).json()
    assert r["lots"][0]["status"] == "DELIVERED" and r["delivered_gpus"] == 128
    r = (await client.patch(f"{V1}/capacity/orders/{o['id']}/lots/{lot1}", json={"actual_operational": "2027-02-20"})).json()
    assert r["operational_gpus"] == 128
    # Delivered lots and orders with deliveries can't be deleted.
    assert (await client.delete(f"{V1}/capacity/orders/{o['id']}/lots/{lot1}")).status_code == 409
    assert (await client.delete(f"{V1}/capacity/orders/{o['id']}")).status_code == 409
    # A lot can't be resized or re-pointed through the generic incoming endpoint.
    assert (await client.patch(f"{V1}/capacity/incoming/{lot1}", json={"quantity": 1})).status_code == 409
    assert (await client.delete(f"{V1}/capacity/incoming/{lot1}")).status_code == 409
    # ...but notes there are fine.
    assert (await client.patch(f"{V1}/capacity/incoming/{lot1}", json={"notes": "burn-in ok"})).status_code == 200


async def test_order_edits_flow_to_lots_and_negotiating_is_not_committed(client: AsyncClient) -> None:
    o = (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "status": "NEGOTIATING"})).json()
    assert o["lots"][0]["status"] == "NEGOTIATING"
    chk = (await client.get(f"{V1}/capacity/check", params={"gpu_model": "B300", "quantity": 1})).json()
    assert chk["incoming"] == 0  # pipeline only
    r = (await client.patch(f"{V1}/capacity/orders/{o['id']}", json={
        "status": "ORDERED", "unit_price_per_server": "800000"})).json()
    assert r["lots"][0]["status"] == "ORDERED" and Decimal(r["total_value"]) == Decimal("51200000.00")
    inc = (await client.get(f"{V1}/capacity/incoming")).json()[0]
    assert Decimal(inc["unit_price"]) == Decimal("100000.00")
    chk = (await client.get(f"{V1}/capacity/check", params={"gpu_model": "B300", "quantity": 1})).json()
    assert chk["incoming"] == 512


async def test_forecast_by_month_for_sales(client: AsyncClient) -> None:
    await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "lots": [
        {"label": "Lote 1", "servers": 16, "expected_delivery": "2027-01-30", "expected_operational": "2027-02-15"},
        {"label": "Lote 2", "servers": 16, "expected_delivery": "2027-04-30"},
        {"label": "Lote 3", "servers": 32},
    ]})
    await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "reference": "Maybe", "servers": 4, "status": "NEGOTIATING"})
    f = (await client.get(f"{V1}/capacity/forecast", params={"months": 6, "today": "2026-11-21"})).json()
    assert f["start_month"] == "2026-11"
    b300 = next(m for m in f["models"] if m["gpu_model"] == "B300")
    assert (b300["contracted"], b300["negotiating"], b300["unscheduled"]) == (512, 32, 256)
    by = {m["month"]: (m["arriving"], m["cumulative"]) for m in b300["months"]}
    assert by["2027-01"] == (0, 0)           # lot 1 counts when operational (Feb)
    assert by["2027-02"] == (128, 128)
    assert by["2027-04"] == (128, 256)
    # Starting later: earlier undelivered lots show as overdue, not lost.
    f2 = (await client.get(f"{V1}/capacity/forecast", params={"months": 3, "today": "2027-03-10"})).json()
    b = next(m for m in f2["models"] if m["gpu_model"] == "B300")
    assert b["overdue"] == 128 and b["months"][0]["cumulative"] == 128


async def test_sales_can_read_but_not_write(client: AsyncClient) -> None:
    from neocloud.auth.dependencies import CurrentUser, get_current_user
    from neocloud.auth.rbac import permissions_for_roles
    from neocloud.main import app

    o = (await client.post(f"{V1}/capacity/orders", json=POSITIVO)).json()
    roles = ["SALES"]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="am", email=None, roles=roles, permissions=permissions_for_roles(roles))
    try:
        assert (await client.get(f"{V1}/capacity/forecast")).status_code == 200
        assert (await client.get(f"{V1}/capacity/orders")).status_code == 200
        assert (await client.post(f"{V1}/capacity/orders", json=POSITIVO)).status_code == 403
        assert (await client.patch(f"{V1}/capacity/orders/{o['id']}", json={"notes": "x"})).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_unknown_supplier_and_bad_input(client: AsyncClient) -> None:
    assert (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "supplier_id": "nope"})).status_code == 404
    assert (await client.post(f"{V1}/capacity/orders", json={**POSITIVO, "servers": 0})).status_code == 422
    assert (await client.get(f"{V1}/capacity/orders/nope")).status_code == 404
