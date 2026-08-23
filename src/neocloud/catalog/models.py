import enum
import uuid
from datetime import date

from sqlalchemy import Boolean, Date, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.common.database import Base, TimestampMixin, UUIDMixin


class SKUCategory(str, enum.Enum):
    GPU = "GPU"
    SERVER = "SERVER"
    STORAGE = "STORAGE"
    NETWORK = "NETWORK"
    CLUSTER = "CLUSTER"
    SERVICE = "SERVICE"


class BillingUnit(str, enum.Enum):
    GPU_HOUR = "GPU_HOUR"
    GPU_MONTH = "GPU_MONTH"
    SERVER_HOUR = "SERVER_HOUR"
    SERVER_MONTH = "SERVER_MONTH"
    GB_HOUR = "GB_HOUR"
    GB_TRANSFERRED = "GB_TRANSFERRED"


class PriceBookType(str, enum.Enum):
    LIST = "LIST"
    REGIONAL = "REGIONAL"
    CUSTOMER = "CUSTOMER"
    CONTRACT = "CONTRACT"
    PROMOTIONAL = "PROMOTIONAL"
    RESERVED = "RESERVED"
    SPOT = "SPOT"


class SKU(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "skus"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[SKUCategory] = mapped_column(Enum(SKUCategory), nullable=False)
    gpu_model: Mapped[str | None] = mapped_column(String(50))
    billing_unit: Mapped[BillingUnit] = mapped_column(Enum(BillingUnit), nullable=False)
    specifications: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    price_entries: Mapped[list["PriceBookEntry"]] = relationship(back_populates="sku")


class PriceBook(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "price_books"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    type: Mapped[PriceBookType] = mapped_column(Enum(PriceBookType), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    entries: Mapped[list["PriceBookEntry"]] = relationship(back_populates="price_book")


class PriceBookEntry(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "price_book_entries"

    price_book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("price_books.id"), nullable=False)
    sku_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("skus.id"), nullable=False)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    minimum_quantity: Mapped[float | None] = mapped_column(Float)
    maximum_quantity: Mapped[float | None] = mapped_column(Float)
    region: Mapped[str | None] = mapped_column(String(50))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    contract_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    price_book: Mapped["PriceBook"] = relationship(back_populates="entries")
    sku: Mapped["SKU"] = relationship(back_populates="price_entries")
