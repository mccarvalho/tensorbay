"""Capacity ledger and availability-check math.

Seeds a minimal inventory hierarchy and a set of H200 GPU assets with varying
operational and commercial statuses, then asserts the derived ledger numbers
and the overselling-prevention check.
"""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.domains.capacity.models import IncomingCapacity
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

V1 = "/v1"


async def _seed_h200_inventory(session: AsyncSession) -> None:
    """Create a single server and attach H200 GPUs with mixed statuses.

    Layout for model H200:
      operational (ONLINE)        : 5
      offline (OFFLINE)           : 1
      maintenance (MAINTENANCE)   : 1
      -> physical = 7
      commercial RESERVED         : 1
      commercial ALLOCATED        : 1
      -> available = operational - reserved - allocated = 5 - 1 - 1 = 3
    Also seed a couple of A100 ONLINE GPUs to prove model filtering.
    """
    region = Region(code="us-e2", name="US East 2")
    dc = Datacenter(code="dc1", name="DC One", region=region)
    cluster = Cluster(code="cl1", name="Cluster One", gpu_model="H200", datacenter=dc)
    rack = Rack(code="rk1", cluster=cluster)
    server = Server(code="srv1", rack=rack)
    session.add(region)

    specs = [
        # (operational_status, commercial_status)
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.ONLINE, CommercialStatus.RESERVED),
        (OperationalStatus.ONLINE, CommercialStatus.ALLOCATED),
        (OperationalStatus.OFFLINE, CommercialStatus.AVAILABLE),
        (OperationalStatus.MAINTENANCE, CommercialStatus.AVAILABLE),
    ]
    for i, (op, comm) in enumerate(specs):
        session.add(
            GpuAsset(
                server=server,
                gpu_id=f"H200-{i}",
                model="H200",
                operational_status=op,
                commercial_status=comm,
            )
        )

    # Decoy model that must not leak into H200 numbers.
    for i in range(2):
        session.add(
            GpuAsset(
                server=server,
                gpu_id=f"A100-{i}",
                model="A100",
                operational_status=OperationalStatus.ONLINE,
                commercial_status=CommercialStatus.AVAILABLE,
            )
        )

    await session.commit()


async def test_capacity_ledger_math(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_h200_inventory(session)

    resp = await client.get(f"{V1}/capacity/ledger", params={"gpu_model": "H200"})
    assert resp.status_code == 200, resp.text
    ledger = resp.json()

    assert ledger["gpu_model"] == "H200"
    assert ledger["physical"] == 7
    assert ledger["offline"] == 1
    assert ledger["maintenance"] == 1
    # operational == count of ONLINE
    assert ledger["operational"] == 5
    assert ledger["reserved"] == 1
    assert ledger["allocated"] == 1
    # available == operational - reserved - allocated
    assert ledger["available"] == ledger["operational"] - ledger["reserved"] - ledger["allocated"]
    assert ledger["available"] == 3


async def test_capacity_check_available(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_h200_inventory(session)

    # Request exactly the available quantity -> AVAILABLE, no gap.
    resp = await client.get(
        f"{V1}/capacity/check", params={"gpu_model": "H200", "quantity": 3}
    )
    assert resp.status_code == 200, resp.text
    check = resp.json()
    assert check["available"] == 3
    assert check["requested"] == 3
    assert check["gap"] == 0
    assert check["status"] == "AVAILABLE"


async def test_capacity_check_unavailable_gap(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_h200_inventory(session)

    # Request far more than available, with no incoming capacity -> UNAVAILABLE
    # and the gap equals requested - available.
    resp = await client.get(
        f"{V1}/capacity/check", params={"gpu_model": "H200", "quantity": 10}
    )
    assert resp.status_code == 200, resp.text
    check = resp.json()
    assert check["available"] == 3
    assert check["requested"] == 10
    assert check["gap"] == 7  # 10 - 3
    assert check["incoming"] == 0
    assert check["status"] == "UNAVAILABLE"


async def test_capacity_check_partial_with_incoming(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed_h200_inventory(session)
    # Add incoming capacity that closes the gap for a request of 10.
    session.add(IncomingCapacity(gpu_model="H200", quantity=20))
    await session.commit()

    resp = await client.get(
        f"{V1}/capacity/check", params={"gpu_model": "H200", "quantity": 10}
    )
    assert resp.status_code == 200, resp.text
    check = resp.json()
    assert check["available"] == 3
    assert check["gap"] == 7
    assert check["incoming"] == 20
    # available(3) < requested(10) but available + incoming(23) >= 10
    assert check["status"] == "PARTIALLY_AVAILABLE"
