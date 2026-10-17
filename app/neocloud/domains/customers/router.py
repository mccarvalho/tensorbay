"""Customer Management API (product plan EPIC 01 / section 7).

CRUD for customers plus nested create/list for contacts and billing accounts.
Reads require CUSTOMER_READ, writes require CUSTOMER_WRITE. Every write is
recorded in the audit trail.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.customers.models import (
    BillingAccount,
    Contact,
    Customer,
)
from neocloud.domains.customers.schemas import (
    BillingAccountCreate,
    BillingAccountResponse,
    BillingAccountUpdate,
    ContactCreate,
    ContactResponse,
    ContactUpdate,
    CustomerCreate,
    CustomerResponse,
    CustomerUpdate,
)

router = APIRouter(prefix="/customers", tags=["Customers"])

ENTITY_CUSTOMER = "customer"
ENTITY_CONTACT = "contact"
ENTITY_BILLING_ACCOUNT = "billing_account"


async def _get_customer_or_404(
    session: AsyncSession, customer_id: str
) -> Customer:
    customer = await session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )
    return customer


# --------------------------------------------------------------------------- #
# Customers
# --------------------------------------------------------------------------- #


@router.get("", response_model=list[CustomerResponse])
async def list_customers(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[Customer]:
    result = await session.execute(
        select(Customer).order_by(Customer.legal_name).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


@router.get("/{customer_id}", response_model=CustomerResponse)
async def get_customer(
    customer_id: str,
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> Customer:
    return await _get_customer_or_404(session, customer_id)


@router.post(
    "", response_model=CustomerResponse, status_code=status.HTTP_201_CREATED
)
async def create_customer(
    payload: CustomerCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> Customer:
    customer = Customer(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(customer)
    await session.flush()
    await session.refresh(customer)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_CUSTOMER,
        entity_id=customer.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return customer


@router.patch("/{customer_id}", response_model=CustomerResponse)
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> Customer:
    customer = await _get_customer_or_404(session, customer_id)
    changes = payload.model_dump(exclude_unset=True)
    old_value = {k: getattr(customer, k) for k in changes}
    for key, value in changes.items():
        setattr(customer, key, value)
    customer.updated_by = user.subject
    await session.flush()
    await session.refresh(customer)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_CUSTOMER,
        entity_id=customer.id,
        actor=user.subject,
        old_value={k: str(v) for k, v in old_value.items()},
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> None:
    customer = await _get_customer_or_404(session, customer_id)
    await session.delete(customer)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_CUSTOMER,
        entity_id=customer_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Contacts (nested under a customer)
# --------------------------------------------------------------------------- #


@router.get(
    "/{customer_id}/contacts", response_model=list[ContactResponse]
)
async def list_contacts(
    customer_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[Contact]:
    await _get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(Contact)
        .where(Contact.customer_id == customer_id)
        .order_by(Contact.name)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post(
    "/{customer_id}/contacts",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_contact(
    customer_id: str,
    payload: ContactCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> Contact:
    await _get_customer_or_404(session, customer_id)
    contact = Contact(
        customer_id=customer_id,
        created_by=user.subject,
        updated_by=user.subject,
        **payload.model_dump(),
    )
    session.add(contact)
    await session.flush()
    await session.refresh(contact)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_CONTACT,
        entity_id=contact.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return contact


@router.patch(
    "/{customer_id}/contacts/{contact_id}", response_model=ContactResponse
)
async def update_contact(
    customer_id: str,
    contact_id: str,
    payload: ContactUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    changes = payload.model_dump(exclude_unset=True)
    old_value = {k: getattr(contact, k) for k in changes}
    for key, value in changes.items():
        setattr(contact, key, value)
    contact.updated_by = user.subject
    await session.flush()
    await session.refresh(contact)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_CONTACT,
        entity_id=contact.id,
        actor=user.subject,
        old_value={k: str(v) for k, v in old_value.items()},
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return contact


@router.delete(
    "/{customer_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_contact(
    customer_id: str,
    contact_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> None:
    contact = await session.get(Contact, contact_id)
    if contact is None or contact.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found"
        )
    await session.delete(contact)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_CONTACT,
        entity_id=contact_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Billing accounts (nested under a customer)
# --------------------------------------------------------------------------- #


@router.get(
    "/{customer_id}/billing-accounts",
    response_model=list[BillingAccountResponse],
)
async def list_billing_accounts(
    customer_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _: CurrentUser = Depends(require_permission(Permission.CUSTOMER_READ)),
) -> list[BillingAccount]:
    await _get_customer_or_404(session, customer_id)
    result = await session.execute(
        select(BillingAccount)
        .where(BillingAccount.customer_id == customer_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post(
    "/{customer_id}/billing-accounts",
    response_model=BillingAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_billing_account(
    customer_id: str,
    payload: BillingAccountCreate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> BillingAccount:
    await _get_customer_or_404(session, customer_id)
    account = BillingAccount(
        customer_id=customer_id,
        created_by=user.subject,
        updated_by=user.subject,
        **payload.model_dump(),
    )
    session.add(account)
    await session.flush()
    await session.refresh(account)
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_BILLING_ACCOUNT,
        entity_id=account.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    return account


@router.patch(
    "/{customer_id}/billing-accounts/{account_id}",
    response_model=BillingAccountResponse,
)
async def update_billing_account(
    customer_id: str,
    account_id: str,
    payload: BillingAccountUpdate,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> BillingAccount:
    account = await session.get(BillingAccount, account_id)
    if account is None or account.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing account not found",
        )
    changes = payload.model_dump(exclude_unset=True)
    old_value = {k: getattr(account, k) for k in changes}
    for key, value in changes.items():
        setattr(account, key, value)
    account.updated_by = user.subject
    await session.flush()
    await session.refresh(account)
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_BILLING_ACCOUNT,
        entity_id=account.id,
        actor=user.subject,
        old_value={k: str(v) for k, v in old_value.items()},
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    return account


@router.delete(
    "/{customer_id}/billing-accounts/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_billing_account(
    customer_id: str,
    account_id: str,
    session: AsyncSession = Depends(get_session),
    user: CurrentUser = Depends(require_permission(Permission.CUSTOMER_WRITE)),
) -> None:
    account = await session.get(BillingAccount, account_id)
    if account is None or account.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Billing account not found",
        )
    await session.delete(account)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_BILLING_ACCOUNT,
        entity_id=account_id,
        actor=user.subject,
    )
