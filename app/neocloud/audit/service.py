"""Audit trail (product plan section 21).

Records WHO/WHEN/ACTION/ENTITY/ENTITY_ID/OLD/NEW/SOURCE/CORRELATION_ID for
every sensitive change.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.core.logging import correlation_id_ctx
from neocloud.db.base import Base, UUIDMixin


class AuditEntry(Base, UUIDMixin):
    __tablename__ = "audit_entries"

    actor: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[dict | None] = mapped_column(JSON)
    new_value: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(64))
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor: str | None = None,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    source: str = "api",
) -> AuditEntry:
    entry = AuditEntry(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        source=source,
        correlation_id=correlation_id_ctx.get(),
    )
    session.add(entry)
    return entry
