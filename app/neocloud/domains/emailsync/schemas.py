from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from neocloud.domains.customers.models import ContactType


class MailboxCreate(BaseModel):
    address: EmailStr
    capture_unmatched: bool = False


class MailboxUpdate(BaseModel):
    enabled: bool | None = None
    capture_unmatched: bool | None = None


class MailboxRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    address: str
    enabled: bool
    capture_unmatched: bool
    connected: bool
    connected_at: datetime | None
    connected_by: str | None
    needs_reconnect: bool
    last_sync_at: datetime | None
    last_error: str | None
    last_logged: int
    total_logged: int


class SyncStatus(BaseModel):
    # True once the Google OAuth client and the token-encryption key are in place.
    configured: bool
    # What to register as the authorized redirect URI in the Google OAuth client.
    redirect_uri: str
    mailboxes: list[MailboxRead]
    pending_unmatched: int


class UnmatchedRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    mailbox: str
    direction: str
    from_addr: str
    external_addrs: str
    subject: str
    body_text: str | None
    sent_at: datetime
    status: str
    resolved_customer_id: str | None


class UnmatchedAssign(BaseModel):
    customer_id: str
    # Also save the sender as a contact so future emails match automatically.
    create_contact: bool = True
    contact_email: EmailStr | None = None  # which external address; default: first
    contact_name: str | None = Field(default=None, max_length=255)
    contact_role: str | None = Field(default=None, max_length=128)
    contact_type: ContactType = ContactType.COMMERCIAL


class SyncRunResult(BaseModel):
    mailbox: str
    logged: int
    unmatched: int
    skipped: int
    error: str | None = None


class ConnectStart(BaseModel):
    authorization_url: str


class ConnectComplete(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048)
    state: str = Field(..., min_length=1, max_length=2048)
