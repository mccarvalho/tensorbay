"""Pydantic v2 schemas for Product Catalog & Pricing."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from neocloud.domains.catalog.models import (
    CommercialModel,
    PriceBookScope,
    SkuCategory,
)

# --------------------------------------------------------------------------- #
# Sku
# --------------------------------------------------------------------------- #


class SkuBase(BaseModel):
    code: str
    name: str
    category: SkuCategory
    gpu_model: str | None = None
    description: str | None = None
    active: bool = True


class SkuCreate(SkuBase):
    pass


class SkuUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    category: SkuCategory | None = None
    gpu_model: str | None = None
    description: str | None = None
    active: bool | None = None


class SkuResponse(SkuBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None


# --------------------------------------------------------------------------- #
# PriceBook
# --------------------------------------------------------------------------- #


class PriceBookBase(BaseModel):
    name: str
    scope: PriceBookScope
    currency: str | None = None
    region: str | None = None
    customer_id: str | None = None


class PriceBookCreate(PriceBookBase):
    pass


class PriceBookUpdate(BaseModel):
    name: str | None = None
    scope: PriceBookScope | None = None
    currency: str | None = None
    region: str | None = None
    customer_id: str | None = None


class PriceBookResponse(PriceBookBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None


# --------------------------------------------------------------------------- #
# Price
# --------------------------------------------------------------------------- #


class PriceBase(BaseModel):
    sku_id: str
    price_book_id: str
    commercial_model: CommercialModel
    unit_price: Decimal
    unit: str
    term_months: int | None = None


class PriceCreate(PriceBase):
    pass


class PriceUpdate(BaseModel):
    sku_id: str | None = None
    price_book_id: str | None = None
    commercial_model: CommercialModel | None = None
    unit_price: Decimal | None = None
    unit: str | None = None
    term_months: int | None = None


class PriceResponse(PriceBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str | None = None
    updated_by: str | None = None
