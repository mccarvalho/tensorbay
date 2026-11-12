"""Email sync models.

A ``Mailbox`` is a Google Workspace mailbox the portal reads (the shared
``crm@`` inbox, and later opt-in sellers). Messages whose participants match a
customer contact become Email activities; ``crm@`` messages that match nobody
land in ``UnmatchedEmail`` for a human to assign.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Integer, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class UnmatchedStatus(StrEnum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    DISMISSED = "DISMISSED"


class Mailbox(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mail_mailboxes"

    address: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # True for the shared crm@ inbox: nothing in it is a seller's private mail, so
    # emails that match no contact are kept for triage. Seller mailboxes keep only
    # emails that match a customer contact and drop the rest.
    capture_unmatched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    history_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Fernet-encrypted Google refresh token, set when the mailbox owner connects it.
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # Google said the grant is gone (revoked / password change): reconnect needed.
    needs_reconnect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    last_logged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_logged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    @property
    def connected(self) -> bool:
        return bool(self.refresh_token_enc)


class UnmatchedEmail(Base, UUIDMixin, AuditMixin):
    __tablename__ = "mail_unmatched"

    mailbox: Mapped[str] = mapped_column(String(320), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    from_addr: Mapped[str] = mapped_column(String(320), nullable=False)
    # Comma-separated external (non-company) addresses seen on the message.
    external_addrs: Mapped[str] = mapped_column(Text, nullable=False, default="")
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UnmatchedStatus.PENDING, index=True
    )
    resolved_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
