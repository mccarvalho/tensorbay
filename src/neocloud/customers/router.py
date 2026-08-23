import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from neocloud.common.auth import CurrentUser, get_current_user, require_permission
from neocloud.common.database import AsyncSession, get_db
from neocloud.common.pagination import PaginatedResponse, PaginationParams
from neocloud.customers.schemas import (
    BillingAccountCreate,
    BillingAccountResponse,
    ContactCreate,
    ContactResponse,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)
from neocloud.customers.service import CustomerService

router = APIRouter()


@router.post("", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED)
async def create_customer(
    data: CustomerCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Create a new customer."""
    service = CustomerService(db)
    return await service.create_customer(data, created_by=user.id)


@router.get("", response_model=PaginatedResponse[CustomerResponse])
async def list_customers(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
    pagination: Annotated[PaginationParams, Depends()],
    search: str | None = None,
    status_filter: str | None = None,
):
    """List customers with optional search and filters."""
    service = CustomerService(db)
    return await service.list_customers(pagination, search=search, status_filter=status_filter)


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
):
    """Get a customer by ID."""
    service = CustomerService(db)
    return await service.get_customer(customer_id)


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Update a customer."""
    service = CustomerService(db)
    return await service.update_customer(customer_id, data)


# --- Contacts ---


@router.post("/{customer_id}/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    customer_id: uuid.UUID,
    data: ContactCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Add a contact to a customer."""
    service = CustomerService(db)
    return await service.create_contact(customer_id, data)


@router.get("/{customer_id}/contacts", response_model=list[ContactResponse])
async def list_contacts(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
):
    """List contacts for a customer."""
    service = CustomerService(db)
    return await service.list_contacts(customer_id)


# --- Billing Accounts ---


@router.post(
    "/{customer_id}/billing-accounts",
    response_model=BillingAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_account(
    customer_id: uuid.UUID,
    data: BillingAccountCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.write"))],
):
    """Create a billing account for a customer."""
    service = CustomerService(db)
    return await service.create_billing_account(customer_id, data)


@router.get("/{customer_id}/billing-accounts", response_model=list[BillingAccountResponse])
async def list_billing_accounts(
    customer_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_permission("customer.read"))],
):
    """List billing accounts for a customer."""
    service = CustomerService(db)
    return await service.list_billing_accounts(customer_id)
