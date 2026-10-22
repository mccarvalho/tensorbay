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

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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


class ArrType(StrEnum):
    """Type of ARR a deal drives. Each role is paid on the ARR it drives."""

    NEW_LOGO = "NEW_LOGO"
    EXPANSION = "EXPANSION"
    RENEWAL = "RENEWAL"


class DealStatus(StrEnum):
    """Lifecycle of a commissionable deal.

    A deal becomes commissionable only after a Super Admin approves the rate,
    finder fee and pricing. PENDING_APPROVAL -> APPROVED | REJECTED.
    """

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class CommissionDeal(Base, UUIDMixin, AuditMixin):
    """A commissionable deal derived from a won opportunity.

    ARR is the annualized revenue (MRR x 12). Gross profit = ARR x margin_pct.
    The deal is created PENDING_APPROVAL; a Super Admin reviews and approves the
    commission rate, finder fee and pricing before it becomes commissionable.
    If the margin at close is below the plan's default (30%), the approval step
    warns the Account Manager and Super Admin.
    """

    __tablename__ = "commission_deals"

    # Source linkage
    opportunity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("commission_plans.id"), nullable=True, index=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    arr_type: Mapped[ArrType] = mapped_column(String(16), nullable=False, default=ArrType.NEW_LOGO)

    # Economics
    arr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    margin_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.30")
    )
    # Persisted gross profit (arr * margin_pct) for reporting/queries.
    gross_profit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    # Credited reps (FK to sales_reps). AE/AM optional; finder only when referred.
    ae_id: Mapped[str | None] = mapped_column(ForeignKey("sales_reps.id"), nullable=True, index=True)
    am_id: Mapped[str | None] = mapped_column(ForeignKey("sales_reps.id"), nullable=True, index=True)
    is_referred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finder_id: Mapped[str | None] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=True, index=True
    )

    # Plan-year attribution (drives the annual quota gate). Derived from booked_date.
    booked_date: Mapped[date] = mapped_column(Date, nullable=False)
    plan_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Approval workflow
    status: Mapped[DealStatus] = mapped_column(
        String(24), nullable=False, default=DealStatus.PENDING_APPROVAL, index=True
    )
    margin_warning: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class RunStatus(StrEnum):
    DRAFT = "DRAFT"  # calculated, under review
    FINALIZED = "FINALIZED"  # locked for payout


class PaymentStatus(StrEnum):
    UNPAID = "UNPAID"
    PAID = "PAID"


class CommissionComponent(StrEnum):
    """Which pool a statement line belongs to."""

    AE = "AE"
    AM = "AM"
    FINDER = "FINDER"


class CommissionRun(Base, UUIDMixin, AuditMixin):
    """A quarterly commission calculation run for a plan year.

    Evaluates each rep's cumulative YTD position against the annual ARR quota
    gate and produces incremental (true-up) statement lines for the quarter.
    """

    __tablename__ = "commission_runs"

    plan_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-4
    plan_id: Mapped[str | None] = mapped_column(
        ForeignKey("commission_plans.id"), nullable=True
    )
    status: Mapped[RunStatus] = mapped_column(
        String(16), nullable=False, default=RunStatus.DRAFT
    )
    # Totals (sum of all statement lines in this run).
    total_commission: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CommissionStatement(Base, UUIDMixin, AuditMixin):
    """A per-rep, per-run line: the incremental commission for the quarter.

    Carries the full breakdown so the number is auditable: the rep's YTD ARR,
    whether the annual gate was cleared, YTD gross profit, YTD earned, prior
    quarters already paid, and the resulting incremental amount.
    """

    __tablename__ = "commission_statements"

    run_id: Mapped[str] = mapped_column(
        ForeignKey("commission_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rep_id: Mapped[str] = mapped_column(
        ForeignKey("sales_reps.id"), nullable=False, index=True
    )
    component: Mapped[CommissionComponent] = mapped_column(String(8), nullable=False)
    plan_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    quarter: Mapped[int] = mapped_column(Integer, nullable=False)

    # Audit breakdown
    ytd_arr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    quota_arr: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=Decimal("0"))
    gate_cleared: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False, default=Decimal("0"))
    ytd_gross_profit: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    ytd_earned: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    prior_paid: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    # The incremental amount owed for THIS quarter (ytd_earned - prior_paid).
    amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )

    # Payment tracking
    payment_status: Mapped[PaymentStatus] = mapped_column(
        String(8), nullable=False, default=PaymentStatus.UNPAID
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
