import enum
import uuid
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class CustomerStatus(str, enum.Enum):
    PROSPECT = "PROSPECT"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CHURNED = "CHURNED"


class CreditStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    LIMITED = "LIMITED"
    BLOCKED = "BLOCKED"


class ContactRole(str, enum.Enum):
    COMMERCIAL = "COMMERCIAL"
    TECHNICAL = "TECHNICAL"
    FINANCE = "FINANCE"
    BILLING = "BILLING"
    EXECUTIVE = "EXECUTIVE"


class BillingAccountStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    CLOSED = "CLOSED"


class TaxConfig(str, enum.Enum):
    TAXABLE = "TAXABLE"
    EXEMPT = "EXEMPT"
    REVERSE_CHARGE = "REVERSE_CHARGE"


class InvoicePreference(str, enum.Enum):
    EMAIL = "EMAIL"
    PORTAL = "PORTAL"
    BOTH = "BOTH"


class Customer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "customers"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    trading_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(50))
    country: Mapped[str] = mapped_column(String(3), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus), default=CustomerStatus.PROSPECT
    )
    credit_status: Mapped[CreditStatus] = mapped_column(
        Enum(CreditStatus), default=CreditStatus.PENDING
    )
    parent_customer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True
    )
    account_owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100))
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    contacts: Mapped[list["Contact"]] = relationship(back_populates="customer", lazy="selectin")
    billing_accounts: Mapped[list["BillingAccount"]] = relationship(back_populates="customer", lazy="selectin")
    children: Mapped[list["Customer"]] = relationship(back_populates="parent", remote_side="Customer.id")
    parent: Mapped["Customer | None"] = relationship(back_populates="children", remote_side=[parent_customer_id])


class Contact(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    role: Mapped[ContactRole] = mapped_column(Enum(ContactRole), nullable=False)
    is_primary: Mapped[bool] = mapped_column(default=False)

    customer: Mapped["Customer"] = relationship(back_populates="contacts")


class BillingAccount(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "billing_accounts"

    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_address_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_address_line2: Mapped[str | None] = mapped_column(String(255))
    billing_city: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_state: Mapped[str | None] = mapped_column(String(100))
    billing_country: Mapped[str] = mapped_column(String(3), nullable=False)
    billing_postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    payment_terms_days: Mapped[int] = mapped_column(default=30)
    credit_limit: Mapped[float | None] = mapped_column(nullable=True)
    tax_config: Mapped[TaxConfig] = mapped_column(Enum(TaxConfig), default=TaxConfig.TAXABLE)
    invoice_preference: Mapped[InvoicePreference] = mapped_column(
        Enum(InvoicePreference), default=InvoicePreference.EMAIL
    )
    status: Mapped[BillingAccountStatus] = mapped_column(
        Enum(BillingAccountStatus), default=BillingAccountStatus.ACTIVE
    )

    customer: Mapped["Customer"] = relationship(back_populates="billing_accounts")
