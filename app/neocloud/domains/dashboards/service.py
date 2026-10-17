"""Dashboard aggregation services (product plan section 17 & 32 KPIs).

All KPIs are derived live from the operational tables (inventory, capacity,
reservations, contracts, sales) so the executive view always reflects the
current source of truth.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.domains.capacity.models import IncomingCapacity
from neocloud.domains.capacity.service import compute_ledger
from neocloud.domains.contracts.models import (
    Commitment,
    CommitmentPeriod,
    Contract,
    ContractStatus,
)
from neocloud.domains.dashboards.schemas import (
    CapacityByModel,
    CommercialKPIs,
    ExecutiveOverview,
    FinanceKPIs,
    FleetKPIs,
)
from neocloud.domains.inventory.models import (
    CommercialStatus,
    GpuAsset,
    OperationalStatus,
)
from neocloud.domains.reservations.models import Reservation, ReservationStatus
from neocloud.domains.sales.models import Opportunity, SalesStage


async def _fleet(session: AsyncSession) -> FleetKPIs:
    stmt = select(
        func.count().label("installed"),
        func.count()
        .filter(GpuAsset.operational_status == OperationalStatus.ONLINE)
        .label("operational"),
        func.count()
        .filter(GpuAsset.commercial_status == CommercialStatus.AVAILABLE)
        .label("available"),
        func.count()
        .filter(GpuAsset.commercial_status == CommercialStatus.RESERVED)
        .label("reserved"),
        func.count()
        .filter(GpuAsset.commercial_status == CommercialStatus.ALLOCATED)
        .label("allocated"),
        func.count()
        .filter(GpuAsset.operational_status == OperationalStatus.MAINTENANCE)
        .label("maintenance"),
        func.count()
        .filter(GpuAsset.operational_status == OperationalStatus.OFFLINE)
        .label("offline"),
        func.count()
        .filter(GpuAsset.operational_status == OperationalStatus.FAILED)
        .label("failed"),
    )
    r = (await session.execute(stmt)).one()
    installed = r.installed or 0
    failed = r.failed or 0
    failure_rate = round((failed / installed * 100), 2) if installed else 0.0
    return FleetKPIs(
        installed_gpus=installed,
        operational_gpus=r.operational or 0,
        available_gpus=r.available or 0,
        reserved_gpus=r.reserved or 0,
        allocated_gpus=r.allocated or 0,
        maintenance_gpus=r.maintenance or 0,
        offline_gpus=r.offline or 0,
        failed_gpus=failed,
        failure_rate_pct=failure_rate,
    )


async def _capacity_by_model(session: AsyncSession) -> list[CapacityByModel]:
    models = (
        await session.execute(select(GpuAsset.model).distinct())
    ).scalars().all()

    out: list[CapacityByModel] = []
    for model in sorted(models):
        ledger = await compute_ledger(session, model)
        incoming = int(
            (
                await session.execute(
                    select(
                        func.coalesce(func.sum(IncomingCapacity.quantity), 0)
                    ).where(IncomingCapacity.gpu_model == model)
                )
            ).scalar_one()
        )
        out.append(
            CapacityByModel(
                gpu_model=model,
                physical=ledger.physical,
                operational=ledger.operational,
                reserved=ledger.reserved,
                allocated=ledger.allocated,
                available=ledger.available,
                incoming=incoming,
            )
        )
    return out


_ACTIVE_CONTRACT_STATUSES = (
    ContractStatus.ACTIVE,
    ContractStatus.AMENDED,
    ContractStatus.RENEWED,
)


async def _commercial(session: AsyncSession) -> CommercialKPIs:
    # Reserved GPUs across active reservations (commercial commitments).
    reserved_gpus = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Reservation.quantity), 0)).where(
                    Reservation.status.in_(
                        (ReservationStatus.ACTIVE, ReservationStatus.PENDING)
                    )
                )
            )
        ).scalar_one()
    )

    # Contracted GPUs = sum of reservation quantities tied to active contracts.
    contracted_gpus = int(
        (
            await session.execute(
                select(func.coalesce(func.sum(Reservation.quantity), 0))
                .select_from(Reservation)
                .join(Contract, Contract.id == Reservation.contract_id)
                .where(Contract.status.in_(_ACTIVE_CONTRACT_STATUSES))
            )
        ).scalar_one()
    )

    active_contracts = int(
        (
            await session.execute(
                select(func.count())
                .select_from(Contract)
                .where(Contract.status.in_(_ACTIVE_CONTRACT_STATUSES))
            )
        ).scalar_one()
    )

    # Pipeline demand from open opportunities (not WON/LOST).
    open_stages = (
        SalesStage.PROSPECTING,
        SalesStage.QUALIFICATION,
        SalesStage.PROPOSAL,
        SalesStage.NEGOTIATION,
    )
    opp_rows = (
        await session.execute(
            select(Opportunity.quantity, Opportunity.probability).where(
                Opportunity.sales_stage.in_(open_stages)
            )
        )
    ).all()
    pipeline_demand = sum(q for q, _ in opp_rows)
    weighted_demand = sum(q * (p / 100.0) for q, p in opp_rows)

    return CommercialKPIs(
        contracted_gpus=contracted_gpus,
        reserved_gpus=reserved_gpus,
        active_contracts=active_contracts,
        pipeline_gpu_demand=pipeline_demand,
        weighted_pipeline_gpu_demand=round(weighted_demand, 2),
        open_opportunities=len(opp_rows),
    )


async def _finance(session: AsyncSession) -> FinanceKPIs:
    # MRR from active contracts' monthly minimum-spend commitments.
    monthly = (
        await session.execute(
            select(func.coalesce(func.sum(Commitment.amount), 0))
            .select_from(Commitment)
            .join(Contract, Contract.id == Commitment.contract_id)
            .where(
                Contract.status.in_(_ACTIVE_CONTRACT_STATUSES),
                Commitment.period == CommitmentPeriod.MONTHLY,
            )
        )
    ).scalar_one()
    annual = (
        await session.execute(
            select(func.coalesce(func.sum(Commitment.amount), 0))
            .select_from(Commitment)
            .join(Contract, Contract.id == Commitment.contract_id)
            .where(
                Contract.status.in_(_ACTIVE_CONTRACT_STATUSES),
                Commitment.period == CommitmentPeriod.ANNUAL,
            )
        )
    ).scalar_one()

    mrr = Decimal(monthly) + (Decimal(annual) / Decimal(12))
    arr = mrr * Decimal(12)

    # Weighted pipeline MRR from open opportunities.
    open_stages = (
        SalesStage.PROSPECTING,
        SalesStage.QUALIFICATION,
        SalesStage.PROPOSAL,
        SalesStage.NEGOTIATION,
    )
    opp_rows = (
        await session.execute(
            select(Opportunity.expected_mrr, Opportunity.probability).where(
                Opportunity.sales_stage.in_(open_stages)
            )
        )
    ).all()
    weighted_pipeline_mrr = sum(
        (Decimal(m) * Decimal(p) / Decimal(100) for m, p in opp_rows),
        Decimal(0),
    )

    return FinanceKPIs(
        mrr=mrr.quantize(Decimal("0.01")),
        arr=arr.quantize(Decimal("0.01")),
        contracted_arr=arr.quantize(Decimal("0.01")),
        revenue_backlog=arr.quantize(Decimal("0.01")),
        weighted_pipeline_mrr=weighted_pipeline_mrr.quantize(Decimal("0.01")),
    )


async def build_overview(session: AsyncSession) -> ExecutiveOverview:
    return ExecutiveOverview(
        fleet=await _fleet(session),
        capacity=await _capacity_by_model(session),
        commercial=await _commercial(session),
        finance=await _finance(session),
    )
