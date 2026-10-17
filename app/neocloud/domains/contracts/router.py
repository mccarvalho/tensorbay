"""Contract Management router (prefix /contracts).

Reads require CONTRACT_READ; writes require CONTRACT_WRITE. Provides CRUD for
contracts plus nested item / commitment / price-agreement management. Every
write is recorded in the audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.contracts import models, schemas

router = APIRouter(prefix="/contracts", tags=["Contracts"])

_CONTRACT_LOADERS = (
    selectinload(models.Contract.items),
    selectinload(models.Contract.commitments),
    selectinload(models.Contract.price_agreements),
)


async def _get_contract_full(session: AsyncSession, contract_id: str) -> models.Contract:
    result = await session.execute(
        select(models.Contract)
        .options(*_CONTRACT_LOADERS)
        .where(models.Contract.id == contract_id)
    )
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    return obj


# --------------------------------------------------------------------------- #
# Contracts (CRUD)
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[schemas.ContractRead])
async def list_contracts(
    customer_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> list[models.Contract]:
    stmt = (
        select(models.Contract)
        .options(*_CONTRACT_LOADERS)
        .order_by(models.Contract.created_at.desc())
    )
    if customer_id is not None:
        stmt = stmt.where(models.Contract.customer_id == customer_id)
    result = await session.execute(stmt.limit(limit).offset(offset))
    return list(result.scalars().all())


@router.get("/{contract_id}", response_model=schemas.ContractRead)
async def get_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CONTRACT_READ)),
) -> models.Contract:
    return await _get_contract_full(session, contract_id)


@router.post("", response_model=schemas.ContractRead, status_code=status.HTTP_201_CREATED)
async def create_contract(
    payload: schemas.ContractCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.Contract:
    data = payload.model_dump(exclude={"items", "commitments", "price_agreements"})
    obj = models.Contract(
        **data,
        tenant_id=user.tenant_id,
        created_by=user.subject,
        updated_by=user.subject,
    )
    for item in payload.items:
        obj.items.append(
            models.ContractItem(
                **item.model_dump(), created_by=user.subject, updated_by=user.subject
            )
        )
    for c in payload.commitments:
        obj.commitments.append(
            models.Commitment(
                **c.model_dump(), created_by=user.subject, updated_by=user.subject
            )
        )
    for pa in payload.price_agreements:
        obj.price_agreements.append(
            models.PriceAgreement(
                **pa.model_dump(), created_by=user.subject, updated_by=user.subject
            )
        )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Contract",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return await _get_contract_full(session, obj.id)


@router.patch("/{contract_id}", response_model=schemas.ContractRead)
async def update_contract(
    contract_id: str,
    payload: schemas.ContractUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.Contract:
    obj = await session.get(models.Contract, contract_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    obj.updated_by = user.subject

    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type="Contract",
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return await _get_contract_full(session, contract_id)


@router.delete("/{contract_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contract(
    contract_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    obj = await session.get(models.Contract, contract_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type="Contract",
        entity_id=contract_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Nested: Items
# --------------------------------------------------------------------------- #


@router.post(
    "/{contract_id}/items",
    response_model=schemas.ContractItemRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_contract_item(
    contract_id: str,
    payload: schemas.ContractItemCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.ContractItem:
    contract = await session.get(models.Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    item = models.ContractItem(
        contract_id=contract_id,
        **payload.model_dump(),
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(item)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="ContractItem",
        entity_id=item.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(item)
    return item


@router.delete(
    "/{contract_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_contract_item(
    contract_id: str,
    item_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    item = await session.get(models.ContractItem, item_id)
    if item is None or item.contract_id != contract_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract item not found")
    await session.delete(item)
    await record_audit(
        session,
        action="delete",
        entity_type="ContractItem",
        entity_id=item_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Nested: Commitments
# --------------------------------------------------------------------------- #


@router.post(
    "/{contract_id}/commitments",
    response_model=schemas.CommitmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_commitment(
    contract_id: str,
    payload: schemas.CommitmentCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.Commitment:
    contract = await session.get(models.Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    commitment = models.Commitment(
        contract_id=contract_id,
        **payload.model_dump(),
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(commitment)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="Commitment",
        entity_id=commitment.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(commitment)
    return commitment


@router.delete(
    "/{contract_id}/commitments/{commitment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_commitment(
    contract_id: str,
    commitment_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    commitment = await session.get(models.Commitment, commitment_id)
    if commitment is None or commitment.contract_id != contract_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commitment not found")
    await session.delete(commitment)
    await record_audit(
        session,
        action="delete",
        entity_type="Commitment",
        entity_id=commitment_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Nested: Price agreements
# --------------------------------------------------------------------------- #


@router.post(
    "/{contract_id}/price-agreements",
    response_model=schemas.PriceAgreementRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_price_agreement(
    contract_id: str,
    payload: schemas.PriceAgreementCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> models.PriceAgreement:
    contract = await session.get(models.Contract, contract_id)
    if contract is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contract not found")
    pa = models.PriceAgreement(
        contract_id=contract_id,
        **payload.model_dump(),
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(pa)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type="PriceAgreement",
        entity_id=pa.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(pa)
    return pa


@router.delete(
    "/{contract_id}/price-agreements/{agreement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_price_agreement(
    contract_id: str,
    agreement_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CONTRACT_WRITE)),
) -> None:
    pa = await session.get(models.PriceAgreement, agreement_id)
    if pa is None or pa.contract_id != contract_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Price agreement not found")
    await session.delete(pa)
    await record_audit(
        session,
        action="delete",
        entity_type="PriceAgreement",
        entity_id=agreement_id,
        actor=user.subject,
    )
