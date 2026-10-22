from httpx import AsyncClient

V1 = "/v1"


async def test_sales_rep_crud(client: AsyncClient) -> None:
    create = await client.post(
        f"{V1}/economics/reps",
        json={
            "name": "Alice Executive",
            "email": "alice@tensorbay.io",
            "type": "AE",
            "base_salary": "150000.00",
        },
    )
    assert create.status_code == 201, create.text
    rep = create.json()
    assert rep["type"] == "AE"
    assert rep["status"] == "ACTIVE"
    rep_id = rep["id"]

    # A finder with no portal access / no salary
    finder = await client.post(
        f"{V1}/economics/reps",
        json={"name": "Partner Co", "type": "FINDER"},
    )
    assert finder.status_code == 201, finder.text

    # Filter by type
    aes = await client.get(f"{V1}/economics/reps", params={"type": "AE"})
    assert aes.status_code == 200
    assert any(r["id"] == rep_id for r in aes.json())
    assert all(r["type"] == "AE" for r in aes.json())

    # Update
    upd = await client.patch(
        f"{V1}/economics/reps/{rep_id}", json={"status": "INACTIVE"}
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "INACTIVE"


async def test_commission_plan_defaults_match_fy2026(client: AsyncClient) -> None:
    create = await client.post(
        f"{V1}/economics/plans",
        json={"name": "FY2026 Plan", "plan_year": 2026},
    )
    assert create.status_code == 201, create.text
    plan = create.json()
    # Defaults encode the TensorBay Commission Plan FY2026.
    assert plan["ae_rate"] == "0.1000"
    assert plan["am_rate"] == "0.1000"
    assert plan["finder_rate"] == "0.0300"
    assert plan["ae_quota_arr"] == "6000000.00"
    assert plan["am_quota_arr"] == "3000000.00"
    assert plan["default_margin_pct"] == "0.3000"
    assert plan["is_active"] is True

    # Fetch active-only for the year
    listed = await client.get(
        f"{V1}/economics/plans", params={"plan_year": 2026, "active_only": True}
    )
    assert listed.status_code == 200
    assert any(p["id"] == plan["id"] for p in listed.json())


async def _plan_and_reps(client: AsyncClient):
    await client.post(
        f"{V1}/economics/plans",
        json={"name": "FY2026", "plan_year": 2026},
    )
    ae = (await client.post(f"{V1}/economics/reps", json={"name": "AE One", "type": "AE", "email": "ae@tensorbay.io"})).json()
    am = (await client.post(f"{V1}/economics/reps", json={"name": "AM One", "type": "AM", "email": "am@tensorbay.io"})).json()
    finder = (await client.post(f"{V1}/economics/reps", json={"name": "Finder", "type": "FINDER"})).json()
    return ae, am, finder


async def test_deal_gross_profit_matches_worked_example(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # Worked example: $12M ARR @ 30% margin -> $3.6M gross profit.
    create = await client.post(
        f"{V1}/economics/deals",
        json={
            "name": "BigCo cluster",
            "customer_id": "cust-1",
            "arr": "12000000.00",
            "margin_pct": "0.30",
            "arr_type": "NEW_LOGO",
            "ae_id": ae["id"],
            "am_id": am["id"],
            "booked_date": "2026-03-15",
        },
    )
    assert create.status_code == 201, create.text
    deal = create.json()
    assert deal["gross_profit"] == "3600000.00"
    assert deal["plan_year"] == 2026
    assert deal["status"] == "PENDING_APPROVAL"
    assert deal["margin_warning"] is False  # 30% == default, not below


async def test_margin_warning_blocks_approval_until_acknowledged(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # Sub-30% margin deal -> margin_warning True
    deal = (
        await client.post(
            f"{V1}/economics/deals",
            json={
                "name": "ThinMargin deal",
                "customer_id": "cust-2",
                "arr": "1000000.00",
                "margin_pct": "0.22",
                "am_id": am["id"],
                "booked_date": "2026-05-01",
            },
        )
    ).json()
    assert deal["margin_warning"] is True

    # Approving without acknowledging the warning is rejected (422).
    blocked = await client.post(
        f"{V1}/economics/deals/{deal['id']}/approve", json={}
    )
    assert blocked.status_code == 422, blocked.text

    # Acknowledge -> approved.
    ok = await client.post(
        f"{V1}/economics/deals/{deal['id']}/approve",
        json={"acknowledge_margin_warning": True},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "APPROVED"
    assert ok.json()["approved_at"] is not None


async def test_deal_approve_and_reject_flow(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    deal = (
        await client.post(
            f"{V1}/economics/deals",
            json={
                "name": "Healthy deal",
                "customer_id": "cust-3",
                "arr": "2000000.00",
                "margin_pct": "0.35",
                "ae_id": ae["id"],
                "booked_date": "2026-06-01",
            },
        )
    ).json()
    assert deal["margin_warning"] is False
    # Healthy margin approves without acknowledgment.
    ok = await client.post(f"{V1}/economics/deals/{deal['id']}/approve", json={})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "APPROVED"
    # Cannot edit an approved deal.
    edit = await client.patch(
        f"{V1}/economics/deals/{deal['id']}", json={"arr": "3000000.00"}
    )
    assert edit.status_code == 409

    # Reject flow on a fresh pending deal.
    deal2 = (
        await client.post(
            f"{V1}/economics/deals",
            json={
                "name": "To reject",
                "customer_id": "cust-4",
                "arr": "500000.00",
                "margin_pct": "0.40",
                "booked_date": "2026-06-01",
            },
        )
    ).json()
    rej = await client.post(
        f"{V1}/economics/deals/{deal2['id']}/reject", json={"reason": "pricing not final"}
    )
    assert rej.status_code == 200
    assert rej.json()["status"] == "REJECTED"
    assert rej.json()["rejection_reason"] == "pricing not final"


async def test_rep_in_use_delete_returns_409(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    await client.post(
        f"{V1}/economics/deals",
        json={
            "name": "Deal using AE",
            "customer_id": "cust-9",
            "arr": "1000000.00",
            "margin_pct": "0.35",
            "ae_id": ae["id"],
            "booked_date": "2026-02-01",
        },
    )
    # The AE is referenced by a deal -> delete must be a clean 409, not 500.
    resp = await client.delete(f"{V1}/economics/reps/{ae['id']}")
    assert resp.status_code == 409, resp.text
    # A rep not on any deal deletes fine.
    resp2 = await client.delete(f"{V1}/economics/reps/{finder['id']}")
    assert resp2.status_code == 204


async def _approved_deal(client, *, name, arr, margin, booked, ae=None, am=None, referred=False, finder=None):
    body = {
        "name": name,
        "customer_id": "cust-x",
        "arr": arr,
        "margin_pct": margin,
        "booked_date": booked,
        "is_referred": referred,
    }
    if ae:
        body["ae_id"] = ae
    if am:
        body["am_id"] = am
    if finder:
        body["finder_id"] = finder
    d = (await client.post(f"{V1}/economics/deals", json=body)).json()
    # Approve (healthy margins here never trip the guardrail).
    await client.post(f"{V1}/economics/deals/{d['id']}/approve", json={})
    return d


async def test_quarterly_run_worked_example(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # $12M ARR @ 30% margin -> $3.6M GP. AE+AM above quota ($6M/$3M), referred.
    await _approved_deal(
        client, name="BigCo", arr="12000000.00", margin="0.30",
        booked="2026-02-01", ae=ae["id"], am=am["id"], referred=True, finder=finder["id"],
    )
    run = (
        await client.post(f"{V1}/economics/runs", json={"plan_year": 2026, "quarter": 1})
    ).json()
    by_component = {s["component"]: s for s in run["statements"]}
    # AE: 10% of $3.6M = $360K, gate cleared ($12M >= $6M)
    assert by_component["AE"]["amount"] == "360000.00"
    assert by_component["AE"]["gate_cleared"] is True
    # AM: 10% of $3.6M = $360K, gate cleared ($12M >= $3M)
    assert by_component["AM"]["amount"] == "360000.00"
    # Finder: 3% of $3.6M = $108K, no gate
    assert by_component["FINDER"]["amount"] == "108000.00"
    # Run total = 360K + 360K + 108K = 828K
    assert run["total_commission"] == "828000.00"


async def test_annual_gate_blocks_below_quota(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # AE books only $2M ARR (< $6M quota) -> $0 commission despite GP.
    await _approved_deal(
        client, name="Small", arr="2000000.00", margin="0.30",
        booked="2026-02-01", ae=ae["id"],
    )
    run = (
        await client.post(f"{V1}/economics/runs", json={"plan_year": 2026, "quarter": 1})
    ).json()
    ae_line = next(s for s in run["statements"] if s["component"] == "AE")
    assert ae_line["gate_cleared"] is False
    assert ae_line["amount"] == "0.00"
    assert ae_line["ytd_earned"] == "0.00"


async def test_quarterly_true_up_when_gate_clears_later(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # Q1: AE books $4M (< $6M) -> Q1 run pays $0.
    await _approved_deal(
        client, name="Q1 deal", arr="4000000.00", margin="0.30",
        booked="2026-02-01", ae=ae["id"],
    )
    run_q1 = (
        await client.post(f"{V1}/economics/runs", json={"plan_year": 2026, "quarter": 1})
    ).json()
    ae_q1 = next(s for s in run_q1["statements"] if s["component"] == "AE")
    assert ae_q1["amount"] == "0.00"
    assert ae_q1["gate_cleared"] is False

    # Q2: AE books another $4M -> YTD $8M clears the $6M gate.
    # YTD GP = $8M * 30% = $2.4M; YTD earned = 10% = $240K; prior paid $0 -> pay $240K.
    await _approved_deal(
        client, name="Q2 deal", arr="4000000.00", margin="0.30",
        booked="2026-05-01", ae=ae["id"],
    )
    run_q2 = (
        await client.post(f"{V1}/economics/runs", json={"plan_year": 2026, "quarter": 2})
    ).json()
    ae_q2 = next(s for s in run_q2["statements"] if s["component"] == "AE")
    assert ae_q2["gate_cleared"] is True
    assert ae_q2["ytd_earned"] == "240000.00"
    assert ae_q2["prior_paid"] == "0.00"
    assert ae_q2["amount"] == "240000.00"


async def test_statement_mark_paid(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    await _approved_deal(
        client, name="PayMe", arr="7000000.00", margin="0.30",
        booked="2026-02-01", ae=ae["id"],
    )
    run = (
        await client.post(f"{V1}/economics/runs", json={"plan_year": 2026, "quarter": 1})
    ).json()
    ae_line = next(s for s in run["statements"] if s["component"] == "AE")
    assert ae_line["amount"] == "210000.00"  # 10% of (7M*30%=2.1M)
    paid = await client.post(
        f"{V1}/economics/statements/{ae_line['id']}/mark-paid",
        json={"payment_reference": "WIRE-123"},
    )
    assert paid.status_code == 200
    assert paid.json()["payment_status"] == "PAID"
    assert paid.json()["payment_reference"] == "WIRE-123"


async def test_cost_items_and_real_margin(client: AsyncClient) -> None:
    ae, am, finder = await _plan_and_reps(client)
    # A $10M ARR deal nominally at 30%.
    deal = (
        await client.post(
            f"{V1}/economics/deals",
            json={
                "name": "RealMargin deal",
                "customer_id": "cust-rm",
                "arr": "10000000.00",
                "margin_pct": "0.30",
                "ae_id": ae["id"],
                "booked_date": "2026-03-01",
            },
        )
    ).json()
    # Allocate $8M total cost (GPU acquisition + colocation) to the deal.
    c1 = await client.post(
        f"{V1}/economics/costs",
        json={
            "name": "H100 cluster purchase",
            "category": "GPU_ACQUISITION",
            "amount": "6000000.00",
            "period": "ONE_TIME",
            "deal_id": deal["id"],
            "customer_id": "cust-rm",
        },
    )
    assert c1.status_code == 201, c1.text
    await client.post(
        f"{V1}/economics/costs",
        json={
            "name": "Colo - annual",
            "category": "COLOCATION",
            "amount": "2000000.00",
            "period": "ANNUAL",
            "deal_id": deal["id"],
        },
    )
    # Real margin: ARR $10M - cost $8M = $2M real GP -> 20% real margin.
    econ = await client.get(f"{V1}/economics/deals/{deal['id']}/economics")
    assert econ.status_code == 200, econ.text
    e = econ.json()
    assert e["allocated_cost"] == "8000000.00"
    assert e["nominal_gross_profit"] == "3000000.00"
    assert e["real_gross_profit"] == "2000000.00"
    assert e["real_margin_pct"] == "0.2000"

    # Filter costs by deal
    listed = await client.get(f"{V1}/economics/costs", params={"deal_id": deal["id"]})
    assert listed.status_code == 200
    assert len(listed.json()) == 2
