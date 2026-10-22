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
