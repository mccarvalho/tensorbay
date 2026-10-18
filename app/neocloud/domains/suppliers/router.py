"""Supplier / Distributor API (procurement counterparties).

CRUD for suppliers plus nested create/list/update/delete for contacts.
Reads require SUPPLIER_READ, writes require SUPPLIER_WRITE. Every write is
recorded in the audit trail.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neocloud.audit.service import record_audit
from neocloud.auth.dependencies import CurrentUser, require_permission
from neocloud.auth.rbac import Permission
from neocloud.db.session import get_session
from neocloud.domains.suppliers.models import Supplier, SupplierContact
from neocloud.domains.suppliers.schemas import (
    SupplierContactCreate,
    SupplierContactRead,
    SupplierContactUpdate,
    SupplierCreate,
    SupplierRead,
    SupplierUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

ReadUser = Annotated[CurrentUser, Depends(require_permission(Permission.SUPPLIER_READ))]
WriteUser = Annotated[
    CurrentUser, Depends(require_permission(Permission.SUPPLIER_WRITE))
]
Session = Annotated[AsyncSession, Depends(get_session)]

ENTITY_SUPPLIER = "supplier"
ENTITY_SUPPLIER_CONTACT = "supplier_contact"


async def _get_supplier_or_404(session: AsyncSession, supplier_id: str) -> Supplier:
    obj = await session.get(Supplier, supplier_id)
    if obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Supplier {supplier_id} not found",
        )
    return obj


async def _get_contact_or_404(
    session: AsyncSession, supplier_id: str, contact_id: str
) -> SupplierContact:
    obj = await session.get(SupplierContact, contact_id)
    if obj is None or obj.supplier_id != supplier_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"SupplierContact {contact_id} not found",
        )
    return obj


# --------------------------------------------------------------------------- #
# Suppliers
# --------------------------------------------------------------------------- #
@router.get("", response_model=list[SupplierRead])
async def list_suppliers(
    session: Session,
    _user: ReadUser,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(Supplier).order_by(Supplier.name)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Supplier.name.ilike(like))
    result = await session.execute(stmt.limit(limit).offset(offset))
    return result.scalars().all()


@router.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier(supplier_id: str, session: Session, _user: ReadUser):
    return await _get_supplier_or_404(session, supplier_id)


@router.post("", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    payload: SupplierCreate, session: Session, user: WriteUser
):
    obj = Supplier(
        **payload.model_dump(), created_by=user.subject, updated_by=user.subject
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_SUPPLIER,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch("/{supplier_id}", response_model=SupplierRead)
async def update_supplier(
    supplier_id: str, payload: SupplierUpdate, session: Session, user: WriteUser
):
    obj = await _get_supplier_or_404(session, supplier_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_SUPPLIER,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: str, session: Session, user: WriteUser):
    obj = await _get_supplier_or_404(session, supplier_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_SUPPLIER,
        entity_id=supplier_id,
        actor=user.subject,
    )


# --------------------------------------------------------------------------- #
# Supplier contacts
# --------------------------------------------------------------------------- #
@router.get("/{supplier_id}/contacts", response_model=list[SupplierContactRead])
async def list_supplier_contacts(
    supplier_id: str, session: Session, _user: ReadUser
):
    await _get_supplier_or_404(session, supplier_id)
    result = await session.execute(
        select(SupplierContact)
        .where(SupplierContact.supplier_id == supplier_id)
        .order_by(SupplierContact.name)
    )
    return result.scalars().all()


@router.post(
    "/{supplier_id}/contacts",
    response_model=SupplierContactRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_supplier_contact(
    supplier_id: str,
    payload: SupplierContactCreate,
    session: Session,
    user: WriteUser,
):
    await _get_supplier_or_404(session, supplier_id)
    obj = SupplierContact(
        supplier_id=supplier_id,
        **payload.model_dump(),
        created_by=user.subject,
        updated_by=user.subject,
    )
    session.add(obj)
    await session.flush()
    await record_audit(
        session,
        action="create",
        entity_type=ENTITY_SUPPLIER_CONTACT,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json"),
    )
    await session.refresh(obj)
    return obj


@router.patch(
    "/{supplier_id}/contacts/{contact_id}", response_model=SupplierContactRead
)
async def update_supplier_contact(
    supplier_id: str,
    contact_id: str,
    payload: SupplierContactUpdate,
    session: Session,
    user: WriteUser,
):
    obj = await _get_contact_or_404(session, supplier_id, contact_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(obj, key, value)
    obj.updated_by = user.subject
    await session.flush()
    await record_audit(
        session,
        action="update",
        entity_type=ENTITY_SUPPLIER_CONTACT,
        entity_id=obj.id,
        actor=user.subject,
        new_value=payload.model_dump(mode="json", exclude_unset=True),
    )
    await session.refresh(obj)
    return obj


@router.delete(
    "/{supplier_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_supplier_contact(
    supplier_id: str, contact_id: str, session: Session, user: WriteUser
):
    obj = await _get_contact_or_404(session, supplier_id, contact_id)
    await session.delete(obj)
    await record_audit(
        session,
        action="delete",
        entity_type=ENTITY_SUPPLIER_CONTACT,
        entity_id=contact_id,
        actor=user.subject,
    )
