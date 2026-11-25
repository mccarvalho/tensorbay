"""Order Form intake: a private link the customer uses to fill in the data TensorBay
needs for the MSA and Order Form (legal entity, signatory, contacts, technical needs)."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class IntakeStatus(StrEnum):
    PENDING = "PENDING"  # link sent, waiting for the customer
    SUBMITTED = "SUBMITTED"  # customer filled it in; the MSA can be generated
    REVOKED = "REVOKED"  # link no longer works


class OrderFormIntake(Base, UUIDMixin, AuditMixin):
    __tablename__ = "order_form_intakes"

    opportunity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    # The link token is a bearer secret: only its hash is used to look it up, and an
    # encrypted copy lets authorised staff copy the link again later.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=IntakeStatus.PENDING)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
