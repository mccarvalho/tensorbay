"""Pydantic schemas for the Order Form intake."""

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

Short = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
Req = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Long = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class ComputeFabric(StrEnum):
    INFINIBAND = "INFINIBAND"
    ROCE = "ROCE"
    NO_PREFERENCE = "NO_PREFERENCE"


class AccessMethod(StrEnum):
    SSH = "SSH"
    VPN = "VPN"
    DIRECT_CONNECT = "DIRECT_CONNECT"


class IntakeSubmission(BaseModel):
    """What the customer fills in. Everything here may end up in the MSA / Order Form."""

    model_config = ConfigDict(extra="forbid")

    # Legal entity (MSA parties clause and Order Form "Customer")
    legal_name: Req
    company_form: Req  # e.g. "limited liability company", "sociedade anônima"
    jurisdiction: Req  # where it is organized, e.g. "Delaware, USA"
    registration_number: Req
    registered_address: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
    website: Short = ""

    # Person who signs
    signatory_name: Req
    signatory_title: Req
    signatory_email: EmailStr

    # Contacts
    notices_email: EmailStr
    technical_contact_name: Short = ""
    technical_contact_email: EmailStr | None = None
    technical_contact_phone: Short = ""
    billing_contact_name: Short = ""
    billing_contact_email: EmailStr | None = None
    billing_contact_phone: Short = ""

    # What they will run and how they connect (Order Form technical rows)
    workload_description: Long = ""
    compute_fabric: ComputeFabric = ComputeFabric.NO_PREFERENCE
    shared_storage_tb: Annotated[int, Field(ge=0, le=100_000)] | None = None
    dedicated_internet_gbps: Annotated[int, Field(ge=0, le=10_000)] | None = None
    monthly_egress_tb: Annotated[int, Field(ge=0, le=1_000_000)] | None = None
    access_methods: list[AccessMethod] = Field(default_factory=list, max_length=3)
    allowed_ip_addresses: Long = ""
    os_image_notes: Long = ""
    region_preference: Short = ""
    preferred_start_date: date | None = None
    additional_notes: Long = ""

    # The customer confirms the data is right.
    confirm_accuracy: bool

    @field_validator("confirm_accuracy")
    @classmethod
    def _must_confirm(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Please confirm the information is accurate")
        return v

    @field_validator("technical_contact_email", "billing_contact_email", mode="before")
    @classmethod
    def _blank_email_is_none(cls, v: object) -> object:
        return None if isinstance(v, str) and not v.strip() else v


class IntakeFormInfo(BaseModel):
    """What the public page shows. No prices and nothing about other customers."""

    status: str  # PENDING | SUBMITTED
    customer_name: str
    gpu_model: str
    quantity: int
    contact_name: str | None
    expires_at: datetime
    submitted_at: datetime | None = None
    prefill: dict | None = None


class IntakeAdmin(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    opportunity_id: str
    status: str
    expired: bool
    expires_at: datetime
    submitted_at: datetime | None
    created_at: datetime
    data: dict | None = None
    token: str | None = None  # only while the link is usable
