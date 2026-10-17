"""Customer Management models (product plan EPIC 01 / section 7).

A Customer is the root commercial entity. It owns Contacts and BillingAccounts
and may form a hierarchy via a self-referencing parent_company_id.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class CustomerStatus(StrEnum):
    PROSPECT = "PROSPECT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class CreditStatus(StrEnum):
    GOOD = "GOOD"
    HOLD = "HOLD"
    BLOCKED = "BLOCKED"


class ContactType(StrEnum):
    COMMERCIAL = "COMMERCIAL"
    TECHNICAL = "TECHNICAL"
    FINANCE = "FINANCE"
    BILLING = "BILLING"
    EXECUTIVE = "EXECUTIVE"


class ActivityType(StrEnum):
    """Pre-proposal engagement / touchpoint types (CRM)."""

    CALL = "CALL"
    EMAIL = "EMAIL"
    MEETING = "MEETING"
    NOTE = "NOTE"
    DEMO = "DEMO"
    OTHER = "OTHER"


class Customer(Base, UUIDMixin, AuditMixin):
    __tablename__ = "customers"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(64), index=True)
    country: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str | None] = mapped_column(String(3))
    status: Mapped[CustomerStatus] = mapped_column(
        String(16), nullable=False, default=CustomerStatus.PROSPECT
    )
    credit_status: Mapped[CreditStatus] = mapped_column(
        String(16), nullable=False, default=CreditStatus.GOOD
    )
    account_owner: Mapped[str | None] = mapped_column(String(255))
    industry: Mapped[str | None] = mapped_column(String(128))
    parent_company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=True, index=True
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )
    billing_accounts: Mapped[list["BillingAccount"]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class Contact(Base, UUIDMixin, AuditMixin):
    __tablename__ = "contacts"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    type: Mapped[ContactType] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(64))

    customer: Mapped["Customer"] = relationship(back_populates="contacts")


class Activity(Base, UUIDMixin, AuditMixin):
    """A CRM touchpoint/interaction with a customer (pre-proposal control)."""

    __tablename__ = "activities"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    type: Mapped[ActivityType] = mapped_column(String(16), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    next_follow_up_date: Mapped[date | None] = mapped_column(
        Date, nullable=True, index=True
    )

    customer: Mapped["Customer"] = relationship(back_populates="activities")


class BillingAccount(Base, UUIDMixin, AuditMixin):
    __tablename__ = "billing_accounts"

    customer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("customers.id"), nullable=False, index=True
    )
    billing_address: Mapped[str | None] = mapped_column(String(512))
    currency: Mapped[str | None] = mapped_column(String(3))
    payment_terms: Mapped[str | None] = mapped_column(String(64))
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    tax_config: Mapped[dict | None] = mapped_column(JSON)
    invoice_preferences: Mapped[dict | None] = mapped_column(JSON)

    customer: Mapped["Customer"] = relationship(
        back_populates="billing_accounts"
    )
