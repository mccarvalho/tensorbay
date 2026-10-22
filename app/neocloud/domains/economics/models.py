"""Economics & Commissions models (TensorBay Commission Plan FY2026).

Pay-on-gross-profit model:
- Account Executive (AE) and Account Manager (AM) each earn 10% of a deal's
  gross profit (GP = ARR x margin). Total internal pool = 20% of GP, split 50/50.
- A 3% of GP finder's fee applies to third-party referred deals (separate pool,
  no quota gate).
- Hard annual ARR quota gate: AE $6M, AM $3M. A rep earns zero commission until
  their annual ARR quota is booked; the gate resets each plan year.
- Default gross margin assumption is 30%; a deal closing below 30% triggers a
  warning to the AM and Super Admin at approval time.

This module holds the foundation entities: the SalesRep registry (AE / AM /
FINDER, who need not be portal users) and the versioned CommissionPlan that
carries the rates, quota gates and default margin for a plan year.
"""

from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from neocloud.db.base import AuditMixin, Base, UUIDMixin


class RepType(StrEnum):
    """The compensation role a rep plays on a deal."""

    AE = "AE"  # Account Executive - wins & grows the account
    AM = "AM"  # Account Manager - owns the customer long-term
    FINDER = "FINDER"  # Third-party referral partner (finder's fee only)


class RepStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class SalesRep(Base, UUIDMixin, AuditMixin):
    """A sales representative or finder.

    Reps are tracked for commission/payment purposes and need not have portal
    access. ``cognito_sub`` optionally links a rep to a Cognito user (the person
    who logs in) so a rep can see their own deals; when null, the rep has no
    portal access but is still paid.
    """

    __tablename__ = "sales_reps"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    type: Mapped[RepType] = mapped_column(String(8), nullable=False)
    status: Mapped[RepStatus] = mapped_column(
        String(16), nullable=False, default=RepStatus.ACTIVE
    )
    # Fixed annual base salary (independent of performance). Informational for
    # AE/AM; typically null for finders.
    base_salary: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    # Optional link to the Cognito user, so a rep who IS a portal user can see
    # their own deals. Null = rep has no portal access.
    cognito_sub: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    # Free-form payment details (bank / PIX / entity) - kept simple for v1.
    payment_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CommissionPlan(Base, UUIDMixin, AuditMixin):
    """Versioned commission plan for a plan year.

    Carries the rates, quota gates and default margin. Only one plan should be
    active per year; rates are reviewed quarterly per the plan's governance.
    All rate/margin fields are fractions (0.10 = 10%).
    """

    __tablename__ = "commission_plans"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Commission rates (share of gross profit).
    ae_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.10")
    )
    am_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.10")
    )
    finder_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.03")
    )

    # Hard annual ARR quota gates (absolute USD amounts).
    ae_quota_arr: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("6000000")
    )
    am_quota_arr: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("3000000")
    )

    # Default gross margin assumption; deals below this at close warn AM + Super Admin.
    default_margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.30")
    )

    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
