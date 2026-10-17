"""Tests for executive/FinOps dashboard aggregations."""

import pytest

from neocloud.domains.contracts.models import (
    Commitment,
    CommitmentPeriod,
    CommitmentType,
    Contract,
    ContractStatus,
)
from neocloud.domains.inventory.models import (
    Cluster,
    CommercialStatus,
    Datacenter,
    GpuAsset,
    OperationalStatus,
    Rack,
    Region,
    Server,
)
from neocloud.domains.sales.models import Opportunity, SalesStage


async def _seed_fleet(session):
    region = Region(code="US-E", name="US East")
    dc = Datacenter(code="DC1", name="DC1", region=region)
    cluster = Cluster(code="C1", name="C1", gpu_model="H200", datacenter=dc)
    rack = Rack(code="R1", cluster=cluster)
    server = Server(code="S1", rack=rack)
    session.add(region)

    # 10 H200: 7 online (2 allocated, 1 reserved, 4 available), 1 maintenance,
    # 1 offline, 1 failed.
    specs = [
        (OperationalStatus.ONLINE, CommercialStatus.ALLOCATED),
        (OperationalStatus.ONLINE, CommercialStatus.ALLOCATED),
        (OperationalStatus.ONLINE, CommercialStatus.RESERVED),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.MAINTENANCE, CommercialStatus.AVAILABLE),
        (OperationalStatus.OFFLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.FAILED, CommercialStatus.AVAILABLE),
    ]
    for i, (op, comm) in enumerate(specs):
        server.gpus.append(
            GpuAsset(
                gpu_id=f"GPU-{i}",
                model="H200",
                operational_status=op,
                commercial_status=comm,
            )
        )
    await session.flush()


@pytest.mark.asyncio
async def test_fleet_kpis(client, session):
    await _seed_fleet(session)
    await session.commit()

    resp = await client.get("/v1/dashboards/fleet")
    assert resp.status_code == 200
    data = resp.json()
    assert data["installed_gpus"] == 10
    assert data["operational_gpus"] == 7
    assert data["allocated_gpus"] == 2
    assert data["reserved_gpus"] == 1
    assert data["available_gpus"] == 7  # commercial_status AVAILABLE count
    assert data["maintenance_gpus"] == 1
    assert data["offline_gpus"] == 1
    assert data["failed_gpus"] == 1
    assert data["failure_rate_pct"] == 10.0  # 1/10


@pytest.mark.asyncio
async def test_finance_mrr_from_commitments(client, session):
    contract = Contract(
        contract_number="CTR-1",
        customer_id="cust-1",
        status=ContractStatus.ACTIVE,
        term_months=12,
    )
    session.add(contract)
    await session.flush()
    session.add(
        Commitment(
            contract_id=contract.id,
            type=CommitmentType.MINIMUM_SPEND,
            amount=200000,
            period=CommitmentPeriod.MONTHLY,
        )
    )
    await session.commit()

    resp = await client.get("/v1/dashboards/finance")
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["mrr"]) == 200000.0
    assert float(data["arr"]) == 2400000.0


@pytest.mark.asyncio
async def test_commercial_pipeline(client, session):
    session.add(
        Opportunity(
            customer_id="cust-1",
            gpu_model="H200",
            quantity=100,
            duration_months=12,
            commercial_model="GPU_MONTHLY",
            expected_mrr=410000,
            probability=70,
            sales_stage=SalesStage.NEGOTIATION,
        )
    )
    await session.commit()

    resp = await client.get("/v1/dashboards/commercial")
    assert resp.status_code == 200
    data = resp.json()
    assert data["pipeline_gpu_demand"] == 100
    assert data["weighted_pipeline_gpu_demand"] == 70.0
    assert data["open_opportunities"] == 1
