import pytest_asyncio
from httpx import AsyncClient

from neocloud.domains.catalog.models import RateCard

V1 = "/v1/capacity/availability"

# The list price as the migration loads it: platform, term, upfront %, US$ per GPU-hour.
RATES = [
    ("B300", 60, 35, "6.50"), ("B300", 60, 65, "6.22"), ("B300", 36, 35, "6.80"), ("B300", 36, 65, "6.44"),
    ("B200", 60, 35, "5.53"), ("B200", 60, 65, "5.29"), ("B200", 36, 35, "5.78"), ("B200", 36, 65, "5.47"),
    ("GB300", 60, 35, "7.20"), ("GB300", 60, 65, "6.89"), ("GB300", 36, 35, "8.80"), ("GB300", 36, 65, "8.33"),
    ("VR200", 60, 40, "10.00"), ("VR200", 36, 40, "11.00"),
]


@pytest_asyncio.fixture
async def rate_card(session):
    session.add_all(RateCard(platform=p, term_months=t, upfront_pct=u, price_per_gpu_hour=pr) for p, t, u, pr in RATES)
    await session.commit()


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
    r = await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "total_qty": 16, "available_qty": 24})
    assert r.status_code == 422
    ok = (await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "total_qty": 16, "available_qty": 16})).json()
    assert (await client.patch(f"{V1}/{ok['id']}", json={"available_qty": 24})).status_code == 422


async def test_gpus_are_sold_in_whole_servers(client: AsyncClient):
    r = await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "available_qty": 100})
    assert r.status_code == 422 and "multiple of 8" in r.text
    assert (await client.post(V1, json={"gpu_model": "B200", "site": "Ohio", "available_qty": 104})).status_code == 201
    racks = await client.post(V1, json={"gpu_model": "VR200", "quantity_unit": "RACKS", "site": "Brazil", "available_qty": 5})
    assert racks.status_code == 201  # racks are not counted in servers


async def test_rate_card_prices_come_with_the_offers_and_the_text(client: AsyncClient, rate_card):
    rc = (await client.get("/v1/pricing/rate-card")).json()
    assert len(rc) == 14
    b300 = {(r["term_months"], int(float(r["upfront_pct"]))): r["price_per_gpu_hour"] for r in rc if r["platform"] == "B300"}
    assert b300 == {(60, 35): "6.50", (60, 65): "6.22", (36, 35): "6.80", (36, 65): "6.44"}
    vr = {(r["term_months"], int(float(r["upfront_pct"]))): r["price_per_gpu_hour"] for r in rc if r["platform"] == "VR200"}
    assert vr == {(60, 40): "10.00", (36, 40): "11.00"}
    o = (await client.post(V1, json={"gpu_model": "HGX B300", "cooling": "AIR", "site": "Brazil", "available_qty": 512})).json()
    assert len(o["rates"]) == 4
    await client.post(V1, json={"gpu_model": "A100", "site": "Chicago", "available_qty": 1400})  # no list price
    listing = (await client.get(V1)).json()
    assert [len(x["rates"]) for x in listing if x["gpu_model"] == "A100"] == [0]
    text = (await client.get(f"{V1}/text")).json()["text"]
    assert "60-month term: 35% upfront US$ 6.50 | 65% upfront US$ 6.22" in text
    assert "36-month term: 35% upfront US$ 6.80 | 65% upfront US$ 6.44" in text
    assert "Minimum order: 32 servers (256 GPUs)" in text


async def test_only_an_admin_changes_a_rate(client: AsyncClient, rate_card):
    from neocloud.auth.dependencies import CurrentUser, get_current_user
    from neocloud.auth.rbac import ROLE_PERMISSIONS, Role
    from neocloud.main import app

    rate = (await client.get("/v1/pricing/rate-card")).json()[0]
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        subject="s", email="s@tensorbay.io", roles=[Role.SALES], permissions=set(ROLE_PERMISSIONS[Role.SALES]))
    try:
        assert (await client.patch(f"/v1/pricing/rate-card/{rate['id']}", json={"price_per_gpu_hour": "1.00"})).status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    r = await client.patch(f"/v1/pricing/rate-card/{rate['id']}", json={"price_per_gpu_hour": "9.99"})
    assert r.status_code == 200 and r.json()["price_per_gpu_hour"] == "9.99"
