"""TensorBay deal phases: order, default probabilities, open/closed, commissions."""

from httpx import AsyncClient

from neocloud.domains.sales.models import OPEN_STAGES, STAGE_PROBABILITY, SalesStage

V1 = "/v1"
ORDER = ["PROSPECTING", "QUALIFICATION", "PROPOSAL", "POC", "NEGOTIATION",
         "SIGNED", "DELIVERY", "ACCEPTANCE", "WON", "LOST"]


def test_phase_order_probabilities_and_open_set() -> None:
    assert [s.value for s in SalesStage] == ORDER
    assert set(STAGE_PROBABILITY) == set(SalesStage)
    probs = [STAGE_PROBABILITY[SalesStage(s)] for s in ORDER[:-1]]
    assert probs == sorted(probs) and probs[-1] == 100  # rises through the funnel
    assert STAGE_PROBABILITY[SalesStage.LOST] == 0
    assert SalesStage.WON not in OPEN_STAGES and SalesStage.LOST not in OPEN_STAGES
    assert {SalesStage.SIGNED, SalesStage.DELIVERY, SalesStage.ACCEPTANCE, SalesStage.POC} <= set(OPEN_STAGES)


async def _opp(client: AsyncClient, stage: str = "PROSPECTING", probability: int = 10, mrr: str = "10000", qty: int = 8) -> dict:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": f"Phase {stage}", "status": "PROSPECT"})).json()["id"]
    r = await client.post(f"{V1}/sales/opportunities", json={
        "customer_id": cid, "gpu_model": "B300", "quantity": qty, "duration_months": 12,
        "commercial_model": "GPU_MONTHLY", "expected_mrr": mrr, "probability": probability, "sales_stage": stage,
    })
    assert r.status_code == 201, r.text
    return r.json()


async def test_moving_sets_the_stage_probability_unless_given(client: AsyncClient) -> None:
    opp = await _opp(client)
    url = f"{V1}/sales/opportunities/{opp['id']}"
    for stage in ORDER[1:9]:
        moved = (await client.patch(url, json={"sales_stage": stage})).json()
        assert (moved["sales_stage"], moved["probability"]) == (stage, STAGE_PROBABILITY[SalesStage(stage)])
    # An explicit probability (the edit form) wins over the default.
    r = (await client.patch(url, json={"sales_stage": "DELIVERY", "probability": 70})).json()
    assert (r["sales_stage"], r["probability"]) == ("DELIVERY", 70)
    # Editing other fields without changing stage keeps a hand-set probability.
    r = (await client.patch(url, json={"sales_stage": "DELIVERY", "quantity": 16})).json()
    assert r["probability"] == 70 and r["quantity"] == 16
    r = (await client.patch(url, json={"probability": 85})).json()
    assert r["probability"] == 85 and r["sales_stage"] == "DELIVERY"


async def test_legacy_negotiation_code_still_works(client: AsyncClient) -> None:
    opp = await _opp(client, stage="NEGOTIATION", probability=60)
    assert opp["sales_stage"] == "NEGOTIATION"
    assert (await client.get(f"{V1}/sales/opportunities/{opp['id']}")).json()["sales_stage"] == "NEGOTIATION"


async def test_dashboards_count_new_open_phases_and_skip_closed(client: AsyncClient) -> None:
    for stage, qty in (("POC", 8), ("SIGNED", 16), ("DELIVERY", 32), ("ACCEPTANCE", 64), ("WON", 128), ("LOST", 256)):
        await _opp(client, stage=stage, probability=STAGE_PROBABILITY[SalesStage(stage)], qty=qty)
    body = (await client.get(f"{V1}/dashboards/executive")).json()
    flat = str(body)
    assert "'pipeline_gpu_demand': 120" in flat, flat  # 8+16+32+64, not WON/LOST
    assert "'open_opportunities': 4" in flat, flat


async def test_only_won_deals_become_commission_deals(client: AsyncClient) -> None:
    """Option (a): a deal counts for commissions only once accepted (WON),
    not at signature or during delivery/acceptance."""
    rep = (await client.post(f"{V1}/economics/reps", json={"name": "AE", "type": "AE"})).json()
    url = f"{V1}/economics/deals/from-opportunity"
    for stage in ("SIGNED", "DELIVERY", "ACCEPTANCE"):
        o = await _opp(client, stage=stage, probability=STAGE_PROBABILITY[SalesStage(stage)])
        r = await client.post(url, json={"opportunity_id": o["id"], "ae_id": rep["id"], "margin_pct": "0.30"})
        assert r.status_code == 400 and "WON" in r.json()["detail"], (stage, r.text)
    won = await _opp(client, stage="WON", probability=100)
    r = await client.post(url, json={"opportunity_id": won["id"], "ae_id": rep["id"], "margin_pct": "0.30"})
    assert r.status_code == 201, r.text
