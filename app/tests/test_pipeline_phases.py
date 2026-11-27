"""TensorBay pipeline: macro stages and substages, hold, escrow, commissions, inventory lanes."""

from httpx import AsyncClient

from neocloud.domains.sales.models import (
    ACTIVE_STAGES,
    MACRO_STAGES,
    OPEN_STAGES,
    STAGE_PROBABILITY,
    SalesStage,
)

V1 = "/v1"
FLOW = [s for _n, (_t, _d, subs) in sorted(MACRO_STAGES.items()) for s in subs]


def test_macro_stages_cover_the_flow_once() -> None:
    assert [m[0] for m in MACRO_STAGES.values()] == ["Lead", "KYC & Contracts", "Payment", "Deployment", "Active Contract"]
    assert len(FLOW) == len(set(FLOW)) == 19
    assert set(FLOW) | {SalesStage.ON_HOLD, SalesStage.LOST} == set(SalesStage)
    assert SalesStage.POC in MACRO_STAGES[1][2]


def test_probabilities_rise_and_open_set() -> None:
    assert set(STAGE_PROBABILITY) == set(SalesStage) - {SalesStage.ON_HOLD}
    probs = [STAGE_PROBABILITY[s] for s in FLOW]
    assert probs == sorted(probs) and probs[-1] == 100
    assert STAGE_PROBABILITY[SalesStage.LOST] == 0
    assert set(ACTIVE_STAGES) == {SalesStage.WON, SalesStage.SUPPORT_SLA, SalesStage.RENEWAL}
    assert not set(OPEN_STAGES) & set(ACTIVE_STAGES)
    assert SalesStage.ON_HOLD not in OPEN_STAGES and SalesStage.LOST not in OPEN_STAGES
    assert {SalesStage.POC, SalesStage.SIGNED, SalesStage.ESCROW_FUNDED, SalesStage.ACCEPTED} <= set(OPEN_STAGES)


async def _opp(client: AsyncClient, stage: str = "NEW_LEAD", probability: int = 10, mrr: str = "10000",
               qty: int = 8, model: str = "B300", **extra) -> dict:
    cid = (await client.post(f"{V1}/customers", json={"legal_name": f"Phase {stage}", "status": "PROSPECT"})).json()["id"]
    r = await client.post(f"{V1}/sales/opportunities", json={
        "customer_id": cid, "gpu_model": model, "quantity": qty, "duration_months": 12,
        "commercial_model": "GPU_MONTHLY", "expected_mrr": mrr, "probability": probability, "sales_stage": stage,
        **extra,
    })
    assert r.status_code == 201, r.text
    return r.json()


async def test_moving_sets_the_stage_probability_unless_given(client: AsyncClient) -> None:
    opp = await _opp(client)
    url = f"{V1}/sales/opportunities/{opp['id']}"
    for stage in FLOW[1:]:
        moved = (await client.patch(url, json={"sales_stage": stage.value})).json()
        assert (moved["sales_stage"], moved["probability"]) == (stage.value, STAGE_PROBABILITY[stage])
    r = (await client.patch(url, json={"sales_stage": "PROVISIONING", "probability": 70})).json()
    assert (r["sales_stage"], r["probability"]) == ("PROVISIONING", 70)
    r = (await client.patch(url, json={"sales_stage": "PROVISIONING", "quantity": 16})).json()
    assert r["probability"] == 70 and r["quantity"] == 16


async def test_on_hold_keeps_probability_and_remembers_the_stage(client: AsyncClient) -> None:
    opp = await _opp(client, stage="UNDER_REVIEW", probability=65)
    url = f"{V1}/sales/opportunities/{opp['id']}"
    held = (await client.patch(url, json={"sales_stage": "ON_HOLD"})).json()
    assert (held["sales_stage"], held["probability"], held["stage_before_hold"]) == ("ON_HOLD", 65, "UNDER_REVIEW")
    resumed = (await client.patch(url, json={"sales_stage": "UNDER_REVIEW"})).json()
    assert resumed["stage_before_hold"] is None and resumed["probability"] == 65


async def test_escrow_substages_are_refused_without_an_escrow_account(client: AsyncClient) -> None:
    opp = await _opp(client, stage="SIGNED", probability=80, escrow_required=False)
    assert opp["escrow_required"] is False
    url = f"{V1}/sales/opportunities/{opp['id']}"
    r = await client.patch(url, json={"sales_stage": "ESCROW_SETUP"})
    assert r.status_code == 422 and "escrow" in r.json()["detail"].lower()
    assert (await client.patch(url, json={"sales_stage": "PROVISIONING"})).status_code == 200
    # Default is escrow on.
    other = await _opp(client, stage="SIGNED", probability=80)
    assert other["escrow_required"] is True
    assert (await client.patch(f"{V1}/sales/opportunities/{other['id']}", json={"sales_stage": "ESCROW_SETUP"})).status_code == 200


async def test_card_fields_roundtrip(client: AsyncClient) -> None:
    opp = await _opp(client, region="Brazil (São Paulo)", assigned_to="Mauricio", next_action="Review MSA & Order Form")
    got = (await client.get(f"{V1}/sales/opportunities/{opp['id']}")).json()
    assert (got["region"], got["assigned_to"], got["next_action"]) == ("Brazil (São Paulo)", "Mauricio", "Review MSA & Order Form")


async def test_dashboards_count_open_phases_and_skip_active_hold_and_lost(client: AsyncClient) -> None:
    for stage, qty in (("POC", 8), ("SIGNED", 16), ("PROVISIONING", 32), ("ACCEPTANCE_TESTING", 64),
                       ("WON", 128), ("SUPPORT_SLA", 256), ("ON_HOLD", 512), ("LOST", 1024)):
        await _opp(client, stage=stage, probability=STAGE_PROBABILITY.get(SalesStage(stage), 50), qty=qty)
    flat = str((await client.get(f"{V1}/dashboards/executive")).json())
    assert "'pipeline_gpu_demand': 120" in flat, flat
    assert "'open_opportunities': 4" in flat, flat


async def test_commissions_only_for_active_contract_stages(client: AsyncClient) -> None:
    """A deal counts for commissions once it is an active contract (WON and after),
    whether or not it went through an escrow account."""
    rep = (await client.post(f"{V1}/economics/reps", json={"name": "AE", "type": "AE"})).json()
    url = f"{V1}/economics/deals/from-opportunity"
    for stage in ("SIGNED", "ESCROW_FUNDED", "PROVISIONING", "ACCEPTED", "ON_HOLD"):
        o = await _opp(client, stage=stage, probability=50)
        r = await client.post(url, json={"opportunity_id": o["id"], "ae_id": rep["id"], "margin_pct": "0.30"})
        assert r.status_code == 400, (stage, r.text)
    for stage, escrow in (("WON", True), ("WON", False), ("SUPPORT_SLA", True)):
        o = await _opp(client, stage=stage, probability=100, escrow_required=escrow)
        r = await client.post(url, json={"opportunity_id": o["id"], "ae_id": rep["id"], "margin_pct": "0.30"})
        assert r.status_code == 201, (stage, escrow, r.text)


async def test_inventory_lanes_show_demand_per_gpu_model(client: AsyncClient) -> None:
    await _opp(client, stage="PROPOSAL_SENT", probability=35, qty=64, model="B300")
    await _opp(client, stage="POC", probability=50, qty=16, model="B300")
    await _opp(client, stage="ON_HOLD", probability=50, qty=1000, model="B300")
    await _opp(client, stage="WON", probability=100, qty=8, model="GB200")
    lanes = {l["gpu_model"]: l for l in (await client.get(f"{V1}/sales/inventory-lanes")).json()}
    assert lanes["B300"]["open_demand"] == 80
    assert lanes["GB200"]["open_demand"] == 0
    for k in ("physical", "allocated", "reserved", "available", "incoming"):
        assert lanes["B300"][k] == 0
