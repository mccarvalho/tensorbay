"""Inbound lead model.

A Lead is the inbox stage *before* a Customer/Opportunity exists: an unqualified
inquiry from the website pricing form. It is routed to an Account Manager by
region, worked (NEW -> CONTACTED -> QUALIFIED), and then either converted into
a Customer (+ optional Opportunity) or disqualified.
"""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class LeadStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    QUALIFIED = "QUALIFIED"
    CONVERTED = "CONVERTED"
    DISQUALIFIED = "DISQUALIFIED"


# Statuses that still count as "open" work for routing load and duplicate checks.
OPEN_STATUSES = (LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.QUALIFIED)


class Lead(Base, UUIDMixin, AuditMixin):
    __tablename__ = "leads"

    # Idempotency key supplied by the website; a retry with the same value never
    # creates a second lead.
    submission_id: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    source: Mapped[str] = mapped_column(
        String(64), nullable=False, default="website_pricing_request"
    )

    # Contact
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Request details
    sku_of_interest: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gpu_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pricing_model_or_term: Mapped[str | None] = mapped_column(String(255), nullable=True)
    site_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Workflow
    status: Mapped[LeadStatus] = mapped_column(
        String(16), nullable=False, default=LeadStatus.NEW, index=True
    )
    assigned_rep_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True, index=True
    )
    # True when the submission was missing something we'd expect (e.g. no
    # recognisable region) so a human should look at it.
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set when an open lead from the same email already exists.
    duplicate_of_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    disqualified_reason: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Conversion links
    converted_customer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    converted_opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Everything the website sent, verbatim (incl. unknown extra fields).
    raw_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
