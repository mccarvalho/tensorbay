"""Declarative base and shared mixins.

The audit mixin supports the Audit Trail requirement (section 21): every
record tracks when it was created/updated and by whom.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class UUIDMixin:
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=_uuid
    )


class AuditMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class TenantMixin:
    """Tenant isolation: customer-scoped rows carry a tenant_id."""

    tenant_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
