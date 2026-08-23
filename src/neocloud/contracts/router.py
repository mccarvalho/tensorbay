import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, require_permission
from neocloud.common.database import AsyncSession, get_db
from neocloud.common.pagination import PaginationParams

router = APIRouter()


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_contract(
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Create a new contract."""
    ...


@router.get("")
async def list_contracts(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.read"))],
    pagination: Annotated[PaginationParams, Depends()],
    customer_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """List contracts with filters."""
    ...


@router.get("/{contract_id}")
async def get_contract(
    contract_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.read"))],
):
    """Get contract details with items, commitments, SLA."""
    ...


@router.post("/{contract_id}/activate", status_code=status.HTTP_200_OK)
async def activate_contract(
    contract_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Activate a contract — creates reservations and updates capacity."""
    ...


@router.post("/{contract_id}/terminate", status_code=status.HTTP_200_OK)
async def terminate_contract(
    contract_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Terminate a contract — releases reservations and capacity."""
    ...


@router.post("/{contract_id}/amend", status_code=status.HTTP_200_OK)
async def amend_contract(
    contract_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Create a contract amendment."""
    ...


@router.post("/{contract_id}/items", status_code=status.HTTP_201_CREATED)
async def add_contract_item(
    contract_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Add a line item to a contract."""
    ...


@router.post("/{contract_id}/commitments", status_code=status.HTTP_201_CREATED)
async def add_commitment(
    contract_id: uuid.UUID,
    data: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("contract.write"))],
):
    """Add a minimum commitment to a contract."""
    ...
