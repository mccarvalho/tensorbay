"""Product Catalog & Pricing models (product plan EPIC 02 / section 8).

A Sku is a sellable item. A PriceBook groups Prices under a scope (list,
regional, customer-specific, etc.). A Price binds a Sku to a PriceBook with a
commercial model and unit price.
"""

from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class SkuCategory(StrEnum):
    GPU = "GPU"
    SERVER = "SERVER"
    CLUSTER = "CLUSTER"
    STORAGE = "STORAGE"
    NETWORK = "NETWORK"


class PriceBookScope(StrEnum):
    LIST = "LIST"
    REGIONAL = "REGIONAL"
    CUSTOMER = "CUSTOMER"
    CONTRACT = "CONTRACT"
    PROMO = "PROMO"
    RESERVED = "RESERVED"
    SPOT = "SPOT"


class CommercialModel(StrEnum):
    GPU_HOURLY = "GPU_HOURLY"
    GPU_MONTHLY = "GPU_MONTHLY"
    SERVER_HOURLY = "SERVER_HOURLY"
    DEDICATED_SERVER = "DEDICATED_SERVER"
    RESERVED = "RESERVED"
    COMMITMENT = "COMMITMENT"
    PREPAID = "PREPAID"
    SPOT = "SPOT"
    PRIVATE_CLUSTER = "PRIVATE_CLUSTER"
    TIERED = "TIERED"
    ENTERPRISE = "ENTERPRISE"
    REVENUE_SHARE = "REVENUE_SHARE"


class Sku(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skus"

    code: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[SkuCategory] = mapped_column(String(16), nullable=False)
    gpu_model: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )

    prices: Mapped[list["Price"]] = relationship(
        back_populates="sku", cascade="all, delete-orphan"
    )


class PriceBook(Base, UUIDMixin, AuditMixin):
    __tablename__ = "price_books"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    scope: Mapped[PriceBookScope] = mapped_column(String(16), nullable=False)
    currency: Mapped[str | None] = mapped_column(String(3))
    region: Mapped[str | None] = mapped_column(String(64))
    customer_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )

    prices: Mapped[list["Price"]] = relationship(
        back_populates="price_book", cascade="all, delete-orphan"
    )


class Price(Base, UUIDMixin, AuditMixin):
    __tablename__ = "prices"

    sku_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("skus.id"), nullable=False, index=True
    )
    price_book_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("price_books.id"), nullable=False, index=True
    )
    commercial_model: Mapped[CommercialModel] = mapped_column(
        String(32), nullable=False
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    term_months: Mapped[int | None] = mapped_column()

    sku: Mapped["Sku"] = relationship(back_populates="prices")
    price_book: Mapped["PriceBook"] = relationship(back_populates="prices")
