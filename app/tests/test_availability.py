from httpx import AsyncClient

V1 = "/v1/capacity/availability"


async def test_availability_list_prices_and_customer_text(client: AsyncClient):
    a = (await client.post(V1, json={"gpu_model": "A100", "site": "Chicago US", "available_qty": 1400})).json()
    b = (await client.post(V1, json={
        "gpu_model": "VR200", "quantity_unit": "RACKS", "site": "Brazil", "available_from": "2027-03-17",
        "total_qty": 32, "available_qty": 16})).json()
    c = (await client.post(V1, json={
        "gpu_model": "B300", "cooling": "AIR", "site": "Brazil", "available_from": "2027-01-01",
        "total_qty": 512, "available_qty": 512, "price_per_gpu_hour": "4.5"})).json()
    assert b["available_from"] == "2027-03-01"  # always the first of the month
    text = (await client.get(f"{V1}/text")).json()["text"]
    assert text.startswith("Immediate Availability\n\nA100\nAvailable at the moment: 1,400 GPUs\nSite: Chicago US")
    assert "January 2027\n\nB300 - Air Cooling\n512 GPUs\nAvailable at the moment: 512 GPUs\nSite: Brazil\nPrice: US$ 4.50 per GPU-hour" in text
    assert "March 2027\n\nVR200\n32 racks\nAvailable at the moment: 16 racks\nSite: Brazil" in text
    assert text.index("Immediate") < text.index("January") < text.index("March")
    # A price is added later, per row.
    r = await client.patch(f"{V1}/{a['id']}", json={"price_per_gpu_hour": "1.25"})
    assert r.status_code == 200 and r.json()["price_per_gpu_hour"] == "1.2500"
    assert "Price: US$ 1.25 per GPU-hour" in (await client.get(f"{V1}/text")).json()["text"]
    assert len((await client.get(V1)).json()) == 3
    assert (await client.delete(f"{V1}/{c['id']}")).status_code == 204


async def test_available_cannot_exceed_total(client: AsyncClient):
    r = await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "total_qty": 10, "available_qty": 11})
    assert r.status_code == 422
    ok = (await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "total_qty": 10, "available_qty": 10})).json()
    assert (await client.patch(f"{V1}/{ok['id']}", json={"available_qty": 12})).status_code == 422
