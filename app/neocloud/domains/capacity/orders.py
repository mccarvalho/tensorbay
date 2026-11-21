"""Supply orders: register a GPU purchase contract by totals, plus its delivery
lots, and expose a month-by-month supply forecast for the commercial team.

An order (e.g. Positivo, 64 x HGX B300 = 512 GPUs) is entered once. Its lots are
IncomingCapacity rows, so the existing capacity ledger and availability checks
count them as incoming supply automatically. No SKU-level assets are created:
servers and GPUs are added to Inventory later, when serial numbers are known.

Reads need capacity.read (sales can see the forecast); writes need
inventory.write, like other incoming-capacity records.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.capacity import schemas
from neocloud.domains.capacity.models import (
    COMMITTED_PROCUREMENT_STATUSES,
    IncomingCapacity,
    ProcurementStatus,
    SupplyOrder,
)
from neocloud.domains.suppliers.models import Supplier

router = APIRouter(prefix="/capacity", tags=["Capacity"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.CAPACITY_READ))]
WriteUser = Annotated[CurrentUser, Depends(require_permission(Permission.INVENTORY_WRITE))]
Session = Annotated[AsyncSession, Depends(get_session)]

ENTITY = "capacity.supply_order"
_ARRIVED = {ProcurementStatus.DELIVERED, ProcurementStatus.OPERATIONAL}
_CENT = Decimal("0.01")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
async def _order_or_404(session: AsyncSession, order_id: str) -> SupplyOrder:
    order = await session.get(SupplyOrder, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Supply order not found")
    return order


async def _lots(session: AsyncSession, order_id: str) -> list[IncomingCapacity]:
    rows = await session.execute(
        select(IncomingCapacity)
        .where(IncomingCapacity.order_id == order_id)
        .order_by(IncomingCapacity.expected_delivery.is_(None), IncomingCapacity.expected_delivery,
                  IncomingCapacity.created_at)
    )
    return list(rows.scalars().all())


def _per_gpu_price(order: SupplyOrder) -> Decimal | None:
    if order.unit_price_per_server is None:
        return None
    return (Decimal(order.unit_price_per_server) / order.gpus_per_server).quantize(_CENT, ROUND_HALF_UP)


def _recompute_totals(order: SupplyOrder, keep_value: bool = False) -> None:
    order.gpus_total = order.servers * order.gpus_per_server
    if keep_value:
        return
    order.total_value = (
        (Decimal(order.unit_price_per_server) * order.servers).quantize(_CENT, ROUND_HALF_UP)
        if order.unit_price_per_server is not None
        else None
    )


def _sync_lot_from_order(lot: IncomingCapacity, order: SupplyOrder) -> None:
    """Lots mirror the order's model, supplier, price and reference."""
    lot.gpu_model = order.gpu_model
    lot.supplier_id = order.supplier_id
    lot.unit_price = _per_gpu_price(order)
    lot.currency = order.currency
    lot.purchase_order = order.reference


def _lot_quantity(order: SupplyOrder, servers: int | None, quantity: int | None) -> int:
    if servers is not None and quantity is not None and servers * order.gpus_per_server != quantity:
        raise HTTPException(
            status_code=422,
            detail=f"{servers} servers is {servers * order.gpus_per_server} GPUs, not {quantity}",
        )
    if servers is not None:
        return servers * order.gpus_per_server
    if quantity is not None:
        return quantity
    raise HTTPException(status_code=422, detail="Give the lot size in servers or GPUs")


def _check_fits(order: SupplyOrder, lots_total: int) -> None:
    if lots_total > order.gpus_total:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Delivery lots add up to {lots_total} GPUs but the order is for "
                f"{order.gpus_total} ({order.servers} servers x {order.gpus_per_server})."
            ),
        )


def _default_lot_status(order: SupplyOrder) -> ProcurementStatus:
    return (
        ProcurementStatus.NEGOTIATING
        if order.status == ProcurementStatus.NEGOTIATING
        else ProcurementStatus.ORDERED
    )


def _serialize(order: SupplyOrder, lots: list[IncomingCapacity]) -> schemas.SupplyOrderRead:
    lot_reads = []
    for lot in lots:
        r = schemas.LotRead.model_validate(lot)
        if lot.quantity % order.gpus_per_server == 0:
            r.servers = lot.quantity // order.gpus_per_server
        lot_reads.append(r)
    in_lots = sum(lot.quantity for lot in lots)
    upcoming = [
        lot.expected_delivery for lot in lots
        if lot.expected_delivery and lot.status not in _ARRIVED
    ]
    out = schemas.SupplyOrderRead.model_validate(order)
    out.lots = lot_reads
    out.scheduled_gpus = sum(lot.quantity for lot in lots if lot.expected_delivery or lot.actual_delivery)
    out.unscheduled_gpus = sum(
        lot.quantity for lot in lots if not (lot.expected_delivery or lot.actual_delivery)
    )
    out.unallocated_gpus = max(order.gpus_total - in_lots, 0)
    out.delivered_gpus = sum(lot.quantity for lot in lots if lot.status in _ARRIVED)
    out.operational_gpus = sum(
        lot.quantity for lot in lots if lot.status == ProcurementStatus.OPERATIONAL
    )
    out.next_delivery = min(upcoming) if upcoming else None
    return out


async def _validate_supplier(session: AsyncSession, supplier_id: str | None) -> None:
    if supplier_id and await session.get(Supplier, supplier_id) is None:
        raise HTTPException(status_code=404, detail="Supplier not found")


# --------------------------------------------------------------------------- #
# Orders
# --------------------------------------------------------------------------- #
@router.get("/orders", response_model=list[schemas.SupplyOrderRead])
async def list_orders(session: Session, _user: ReadUser, gpu_model: str | None = None):
    stmt = select(SupplyOrder).order_by(SupplyOrder.created_at.desc())
    if gpu_model:
        stmt = stmt.where(SupplyOrder.gpu_model == gpu_model)
    orders = (await session.execute(stmt)).scalars().all()
    return [_serialize(o, await _lots(session, o.id)) for o in orders]


@router.get("/orders/{order_id}", response_model=schemas.SupplyOrderRead)
async def get_order(order_id: str, session: Session, _user: ReadUser):
    order = await _order_or_404(session, order_id)
    return _serialize(order, await _lots(session, order.id))


@router.post("/orders", response_model=schemas.SupplyOrderRead, status_code=status.HTTP_201_CREATED)
async def create_order(payload: schemas.SupplyOrderCreate, session: Session, user: WriteUser):
    await _validate_supplier(session, payload.supplier_id)
    data = payload.model_dump(exclude={"lots"})
    data["gpu_model"] = data["gpu_model"].strip()
    order = SupplyOrder(**data, gpus_total=0, created_by=user.subject, updated_by=user.subject)
    _recompute_totals(order, keep_value=payload.total_value is not None)
    session.add(order)
    await session.flush()

    lot_specs = payload.lots or [schemas.LotInput(label="Lot 1", quantity=order.gpus_total)]
    quantities = [_lot_quantity(order, spec.servers, spec.quantity) for spec in lot_specs]
    _check_fits(order, sum(quantities))
    for i, (spec, qty) in enumerate(zip(lot_specs, quantities, strict=True), start=1):
        lot = IncomingCapacity(
            order_id=order.id,
            lot_label=(spec.label or f"Lot {i}").strip(),
            quantity=qty,
            status=spec.status or _default_lot_status(order),
            expected_delivery=spec.expected_delivery,
            expected_operational=spec.expected_operational,
            actual_delivery=spec.actual_delivery,
            actual_operational=spec.actual_operational,
            notes=spec.notes,
            created_by=user.subject,
            updated_by=user.subject,
        )
        _sync_lot_from_order(lot, order)
        session.add(lot)
    await session.flush()
    await record_audit(
        session, action="create", entity_type=ENTITY, entity_id=order.id, actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(order)
    return _serialize(order, await _lots(session, order.id))


@router.patch("/orders/{order_id}", response_model=schemas.SupplyOrderRead)
async def update_order(
    order_id: str, payload: schemas.SupplyOrderUpdate, session: Session, user: WriteUser
):
    order = await _order_or_404(session, order_id)
    changes = payload.model_dump(exclude_unset=True)
    if "supplier_id" in changes:
        await _validate_supplier(session, changes["supplier_id"])
    for key in ("reference", "gpu_model"):
        if key in changes and changes[key] is None:
            raise HTTPException(status_code=422, detail=f"{key} cannot be empty")
    was_negotiating = order.status == ProcurementStatus.NEGOTIATING
    for key, value in changes.items():
        setattr(order, key, value.strip() if isinstance(value, str) and key == "gpu_model" else value)
    # An explicit contract total wins; otherwise recompute when size or price change.
    price_or_size = changes.keys() & {"servers", "gpus_per_server", "unit_price_per_server"}
    _recompute_totals(order, keep_value="total_value" in changes or not price_or_size)
    lots = await _lots(session, order.id)
    _check_fits(order, sum(lot.quantity for lot in lots))
    for lot in lots:
        _sync_lot_from_order(lot, order)
        # Signing a negotiated order makes its lots committed supply.
        if was_negotiating and order.status != ProcurementStatus.NEGOTIATING and lot.status == ProcurementStatus.NEGOTIATING:
            lot.status = ProcurementStatus.ORDERED
        lot.updated_by = user.subject
    order.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="update", entity_type=ENTITY, entity_id=order.id, actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(order)
    return _serialize(order, await _lots(session, order.id))


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_order(order_id: str, session: Session, user: WriteUser) -> None:
    order = await _order_or_404(session, order_id)
    lots = await _lots(session, order.id)
    if any(lot.status in _ARRIVED for lot in lots):
        raise HTTPException(
            status_code=409, detail="Part of this order was already delivered; it can't be deleted"
        )
    for lot in lots:
        await session.delete(lot)
    await session.delete(order)
    await record_audit(
        session, action="delete", entity_type=ENTITY, entity_id=order_id, actor=user.subject
    )


# --------------------------------------------------------------------------- #
# Delivery lots
# --------------------------------------------------------------------------- #
@router.post("/orders/{order_id}/lots", response_model=schemas.SupplyOrderRead,
             status_code=status.HTTP_201_CREATED)
async def add_lot(order_id: str, payload: schemas.LotInput, session: Session, user: WriteUser):
    order = await _order_or_404(session, order_id)
    lots = await _lots(session, order.id)
    qty = _lot_quantity(order, payload.servers, payload.quantity)
    _check_fits(order, sum(lot.quantity for lot in lots) + qty)
    lot = IncomingCapacity(
        order_id=order.id,
        lot_label=(payload.label or f"Lot {len(lots) + 1}").strip(),
        quantity=qty,
        status=payload.status or _default_lot_status(order),
        expected_delivery=payload.expected_delivery,
        expected_operational=payload.expected_operational,
        actual_delivery=payload.actual_delivery,
        actual_operational=payload.actual_operational,
        notes=payload.notes,
        created_by=user.subject,
        updated_by=user.subject,
    )
    _sync_lot_from_order(lot, order)
    session.add(lot)
    await session.flush()
    await record_audit(
        session, action="add_lot", entity_type=ENTITY, entity_id=order.id, actor=user.subject,
        new_value={"lot_id": lot.id, **payload.model_dump(mode="json")},
    )
    return _serialize(order, await _lots(session, order.id))


async def _lot_or_404(session: AsyncSession, order: SupplyOrder, lot_id: str) -> IncomingCapacity:
    lot = await session.get(IncomingCapacity, lot_id)
    if lot is None or lot.order_id != order.id:
        raise HTTPException(status_code=404, detail="Lot not found on this order")
    return lot


@router.patch("/orders/{order_id}/lots/{lot_id}", response_model=schemas.SupplyOrderRead)
async def update_lot(
    order_id: str, lot_id: str, payload: schemas.LotUpdate, session: Session, user: WriteUser
):
    order = await _order_or_404(session, order_id)
    lot = await _lot_or_404(session, order, lot_id)
    changes = payload.model_dump(exclude_unset=True)
    servers = changes.pop("servers", None)
    quantity = changes.pop("quantity", None)
    if servers is not None or quantity is not None:
        new_qty = _lot_quantity(order, servers, quantity)
        others = sum(lt.quantity for lt in await _lots(session, order.id) if lt.id != lot.id)
        _check_fits(order, others + new_qty)
        lot.quantity = new_qty
    if "label" in changes:
        lot.lot_label = (changes.pop("label") or lot.lot_label or "").strip() or lot.lot_label
    for key, value in changes.items():
        setattr(lot, key, value)
    # Recording an actual date implies the matching status (and vice versa is left to the user).
    if lot.actual_operational and lot.status != ProcurementStatus.OPERATIONAL:
        lot.status = ProcurementStatus.OPERATIONAL
    elif lot.actual_delivery and lot.status not in _ARRIVED:
        lot.status = ProcurementStatus.DELIVERED
    lot.updated_by = user.subject
    await session.flush()
    await record_audit(
        session, action="update_lot", entity_type=ENTITY, entity_id=order.id, actor=user.subject,
        new_value={"lot_id": lot.id, **payload.model_dump(mode="json", exclude_unset=True)},
    )
    return _serialize(order, await _lots(session, order.id))


@router.delete("/orders/{order_id}/lots/{lot_id}", response_model=schemas.SupplyOrderRead)
async def delete_lot(order_id: str, lot_id: str, session: Session, user: WriteUser):
    order = await _order_or_404(session, order_id)
    lot = await _lot_or_404(session, order, lot_id)
    if lot.status in _ARRIVED:
        raise HTTPException(status_code=409, detail="A delivered lot can't be deleted")
    await session.delete(lot)
    await session.flush()
    await record_audit(
        session, action="delete_lot", entity_type=ENTITY, entity_id=order.id, actor=user.subject,
        new_value={"lot_id": lot_id},
    )
    return _serialize(order, await _lots(session, order.id))


# --------------------------------------------------------------------------- #
# Forecast (commercial view)
# --------------------------------------------------------------------------- #
def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    return date(d.year + y, m + 1, 1)


@router.get("/forecast", response_model=schemas.SupplyForecast)
async def supply_forecast(
    session: Session,
    _user: ReadUser,
    months: Annotated[int, Query(ge=1, le=36)] = 18,
    today: Annotated[date | None, Query(include_in_schema=False)] = None,
):
    """GPUs becoming available per model, month by month.

    A lot counts in the month it becomes operational (actual date first, then the
    expected operational date, then the expected delivery date). Lots before the
    window that are not delivered yet are reported as ``overdue``; already
    delivered ones are part of the opening cumulative figure.
    """
    start = (today or date.today()).replace(day=1)
    keys = [_month_key(_add_months(start, i)) for i in range(months)]
    rows = (await session.execute(select(IncomingCapacity))).scalars().all()

    per_model: dict[str, dict] = {}
    for r in rows:
        m = per_model.setdefault(r.gpu_model, {
            "contracted": 0, "negotiating": 0, "delivered": 0, "operational": 0,
            "unscheduled": 0, "overdue": 0, "opening": 0, "by_month": dict.fromkeys(keys, 0),
        })
        if r.status not in COMMITTED_PROCUREMENT_STATUSES:
            m["negotiating"] += r.quantity
            continue
        m["contracted"] += r.quantity
        if r.status in _ARRIVED:
            m["delivered"] += r.quantity
        if r.status == ProcurementStatus.OPERATIONAL:
            m["operational"] += r.quantity
        when = r.actual_operational or r.expected_operational or r.actual_delivery or r.expected_delivery
        if when is None:
            m["unscheduled"] += r.quantity
            continue
        key = _month_key(when)
        if key in m["by_month"]:
            m["by_month"][key] += r.quantity
        elif when < start:
            m["opening"] += r.quantity
            if r.status not in _ARRIVED:
                m["overdue"] += r.quantity
        # Beyond the window: counted in contracted only.

    out = []
    for model in sorted(per_model):
        m = per_model[model]
        if not m["contracted"] and not m["negotiating"]:
            continue
        running = m["opening"]
        series = []
        for k in keys:
            running += m["by_month"][k]
            series.append(schemas.ForecastMonth(month=k, arriving=m["by_month"][k], cumulative=running))
        out.append(schemas.ModelForecast(
            gpu_model=model, contracted=m["contracted"], negotiating=m["negotiating"],
            delivered=m["delivered"], operational=m["operational"],
            unscheduled=m["unscheduled"], overdue=m["overdue"], months=series,
        ))
    return schemas.SupplyForecast(start_month=keys[0], months=months, models=out)
