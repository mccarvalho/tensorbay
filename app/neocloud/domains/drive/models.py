"""Google Drive storage for generated documents.

One connection per environment: a Google account (normally crm@tensorbay.io)
whose Drive holds a shared root folder (e.g. "CRM TensorBay"). Documents are
filed under ``Clients/<customer>/<opportunity or contract>/<document type>/``.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class DriveConnection(Base, UUIDMixin, AuditMixin):
    __tablename__ = "drive_connections"

    account_email: Mapped[str] = mapped_column(String(320), nullable=False)
    refresh_token_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    connected_by: Mapped[str | None] = mapped_column(String(320), nullable=True)
    needs_reconnect: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    root_folder_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    root_folder_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    root_folder_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)


class DriveFolder(Base, UUIDMixin, AuditMixin):
    """Cache of folders the portal created/found, keyed by their path under the root."""

    __tablename__ = "drive_folders"

    root_folder_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    folder_id: Mapped[str] = mapped_column(String(128), nullable=False)
