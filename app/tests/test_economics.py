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
