"""Contract Management pydantic schemas (pydantic v2)."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from neocloud.domains.contracts.models import (
    CommitmentPeriod,
    CommitmentType,
    ContractStatus,
)

# --------------------------------------------------------------------------- #
# ContractItem
# --------------------------------------------------------------------------- #


class ContractItemBase(BaseModel):
    sku_id: str
    quantity: int = Field(gt=0)
    unit_price: Decimal
    unit: str


class ContractItemCreate(ContractItemBase):
    pass


class ContractItemRead(ContractItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str


# --------------------------------------------------------------------------- #
# Commitment
# --------------------------------------------------------------------------- #


class CommitmentBase(BaseModel):
    type: CommitmentType
    amount: Decimal
    period: CommitmentPeriod


class CommitmentCreate(CommitmentBase):
    pass


class CommitmentRead(CommitmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str


# --------------------------------------------------------------------------- #
# PriceAgreement
# --------------------------------------------------------------------------- #


class PriceAgreementBase(BaseModel):
    sku_id: str
    agreed_price: Decimal
    unit: str


class PriceAgreementCreate(PriceAgreementBase):
    pass


class PriceAgreementRead(PriceAgreementBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str


# --------------------------------------------------------------------------- #
# Contract
# --------------------------------------------------------------------------- #


class ContractBase(BaseModel):
    contract_number: str
    customer_id: str
    status: ContractStatus = ContractStatus.DRAFT
    term_months: int = Field(gt=0)
    start_date: date | None = None
    end_date: date | None = None
    auto_renew: bool = False
    commercial_notes: str | None = None
    document_reference: str | None = None


class ContractCreate(ContractBase):
    items: list[ContractItemCreate] = Field(default_factory=list)
    commitments: list[CommitmentCreate] = Field(default_factory=list)
    price_agreements: list[PriceAgreementCreate] = Field(default_factory=list)


class ContractUpdate(BaseModel):
    contract_number: str | None = None
    status: ContractStatus | None = None
    term_months: int | None = Field(default=None, gt=0)
    start_date: date | None = None
    end_date: date | None = None
    auto_renew: bool | None = None
    commercial_notes: str | None = None
    document_reference: str | None = None


class ContractRead(ContractBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ContractItemRead] = Field(default_factory=list)
    commitments: list[CommitmentRead] = Field(default_factory=list)
    price_agreements: list[PriceAgreementRead] = Field(default_factory=list)
