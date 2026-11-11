"""Pydantic v2 schemas for inbound leads."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from neocloud.domains.leads.models import LeadStatus

# Fields the website may send as numbers/other scalars; coerce to str first.
_STRINGISH = (
    "company",
    "sku_of_interest",
    "gpu_count",
    "pricing_model_or_term",
    "site_language",
    "region",
    "country",
    "message",
    "page_url",
    "source",
)


class LeadIngest(BaseModel):
    """Payload the website form backend POSTs to /v1/leads/ingest.

    Unknown extra fields are accepted (and stored in ``raw_payload``) so the
    developer can add fields later without breaking ingestion.
    """

    model_config = ConfigDict(extra="allow")

    submission_id: str = Field(..., min_length=1, max_length=128)
    submitted_at: datetime | None = None
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    sku_of_interest: str | None = Field(default=None, max_length=255)
    gpu_count: str | None = Field(default=None, max_length=64)
    pricing_model_or_term: str | None = Field(default=None, max_length=255)
    site_language: str | None = Field(default=None, max_length=16)
    region: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=128)
    message: str | None = Field(default=None, max_length=5000)
    page_url: str | None = Field(default=None, max_length=1024)
    source: str | None = Field(default=None, max_length=64)

    @field_validator(*_STRINGISH, mode="before")
    @classmethod
    def _to_str(cls, v: Any) -> Any:
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v)
        return v


class LeadCreate(BaseModel):
    """A lead entered by hand in the portal (phone call, event, referral, ...)."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    company: str | None = Field(default=None, max_length=255)
    sku_of_interest: str | None = Field(default=None, max_length=255)
    gpu_count: int | None = Field(default=None, gt=0, le=10_000_000)
    pricing_model_or_term: str | None = Field(default=None, max_length=255)
    region: str | None = Field(default=None, max_length=255)
    country: str | None = Field(default=None, max_length=128)
    message: str | None = Field(default=None, max_length=5000)
    source: str | None = Field(default=None, max_length=64)
    # Managers may pick the AM; AMs always get their own leads. Blank = auto-route.
    assigned_rep_id: str | None = None


class LeadIngestResult(BaseModel):
    id: str
    status: str  # "created" | "duplicate"
    assigned_to: str | None = None
    needs_review: bool = False


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    submission_id: str
    source: str
    name: str
    email: str
    company: str | None
    sku_of_interest: str | None
    gpu_count: int | None
    pricing_model_or_term: str | None
    site_language: str | None
    region: str | None
    country: str | None
    message: str | None
    page_url: str | None
    submitted_at: datetime | None
    status: LeadStatus
    assigned_rep_id: str | None
    needs_review: bool
    duplicate_of_id: str | None
    disqualified_reason: str | None
    notes: str | None
    converted_customer_id: str | None
    converted_opportunity_id: str | None
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    """Manual edits. CONVERTED is only reachable via /convert."""

    status: LeadStatus | None = None
    assigned_rep_id: str | None = None
    notes: str | None = None
    needs_review: bool | None = None


class LeadDisqualify(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1024)


class LeadConvert(BaseModel):
    """Convert a lead into a Customer (+Contact, +Activity) and optionally an
    Opportunity. The email rarely carries enough to price a deal, so opportunity
    fields are supplied by the rep at conversion time."""

    customer_name: str | None = Field(default=None, max_length=255)
    create_opportunity: bool = False
    gpu_model: str | None = Field(default=None, max_length=128)
    quantity: int | None = Field(default=None, gt=0)
    duration_months: int | None = Field(default=None, gt=0)
    commercial_model: str | None = Field(default=None, max_length=64)
    expected_mrr: Decimal | None = Field(default=None, ge=0)


class LeadConvertResult(BaseModel):
    lead: LeadRead
    customer_id: str
    contact_id: str | None
    opportunity_id: str | None
    customer_created: bool
