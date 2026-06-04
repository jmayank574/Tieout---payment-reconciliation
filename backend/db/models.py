"""
SQLAlchemy 2.0 ORM models for Tieout.

All primary keys are UUIDs. All money amounts are Decimal.
ground_truth_link.ledger_entry_id is nullable to handle bank_only_noise cases.
"""

from uuid import uuid4
from datetime import datetime, date, timezone
import enum

from sqlalchemy import (
    String, Numeric, DateTime, Date, ForeignKey, Index, Enum, Column, JSON
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

# SQLAlchemy defaults to storing enum member *names* (uppercase) for native
# Postgres types. This helper forces it to use the .value (lowercase) instead,
# so raw SQL and Python both use the same strings.
def _ev(cls):
    return Enum(cls, values_callable=lambda e: [x.value for x in e])


class PlanType(str, enum.Enum):
    """Health plan types."""
    PPO = "ppo"
    HMO = "hmo"
    HDHP = "hdhp"


class GroupStatus(str, enum.Enum):
    """Employer group status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class MemberStatus(str, enum.Enum):
    """Member enrollment status (implicit from enrollment_start/end)."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class BankAccountType(str, enum.Enum):
    """Type of bank account."""
    CLEARING = "clearing"
    OPERATING = "operating"


class ClaimStatus(str, enum.Enum):
    """Claim payment status."""
    PENDING = "pending"
    PAID = "paid"
    VOIDED = "voided"
    REISSUED = "reissued"


class LedgerEntryType(str, enum.Enum):
    """Types of ledger entries (book entries)."""
    EMPLOYER_FUNDING = "employer_funding"
    CLAIM_PAYMENT = "claim_payment"
    STOP_LOSS_PREMIUM = "stop_loss_premium"
    STOP_LOSS_REIMBURSEMENT = "stop_loss_reimbursement"
    ADMIN_FEE = "admin_fee"
    CARD_LOAD = "card_load"
    CARD_SETTLEMENT = "card_settlement"
    ACH_RETURN = "ach_return"
    BANK_FEE = "bank_fee"
    INTEREST = "interest"


class Direction(str, enum.Enum):
    """Debit or credit."""
    DEBIT = "debit"
    CREDIT = "credit"


class LedgerEntryStatus(str, enum.Enum):
    """Ledger entry lifecycle status."""
    EXPECTED = "expected"
    CLEARED = "cleared"


class ReconciliationMatchStatus(str, enum.Enum):
    """Status of a reconciliation match."""
    PENDING = "pending"           # legacy; engine now emits NEEDS_REVIEW
    MATCHED = "matched"           # auto-cleared by engine (confidence >= threshold)
    REVIEWED = "reviewed"         # legacy; unused in Step 4+
    RESOLVED = "resolved"         # fully resolved by operator
    NEEDS_REVIEW = "needs_review" # in the exception queue (engine-created)
    WRITTEN_OFF = "written_off"   # operator declared no ledger counterpart
    FLAGGED = "flagged"           # escalated; stays in queue
    PARTIALLY_RESOLVED = "partially_resolved"  # split where sum < bank amount


class ExceptionType(str, enum.Enum):
    """Exception types (for ground_truth_link)."""
    CLEAN = "clean"
    TIMING = "timing"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_MANY = "one_to_many"
    REVERSAL = "reversal"
    SHORT_OVER_FUNDING = "short_over_funding"
    UNREFERENCED_INBOUND = "unreferenced_inbound"
    BANK_ONLY_NOISE = "bank_only_noise"


# ============================================================================
# Tables
# ============================================================================

class EmployerGroup(Base):
    """Employer groups that hold money in clearing accounts."""
    __tablename__ = "employer_group"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    plan_type = Column(_ev(PlanType), nullable=False)
    status = Column(_ev(GroupStatus), nullable=False, default=GroupStatus.ACTIVE)
    pepm_rate = Column(Numeric(10, 2), nullable=False)
    stop_loss_carrier = Column(String(255), nullable=True)
    funding_bank_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=False)

    # Relationships
    members = relationship("Member", back_populates="group")
    claims = relationship("Claim", back_populates="group")
    ledger_entries = relationship("LedgerEntry", back_populates="group")

    __table_args__ = (
        Index("ix_employer_group_status", "status"),
    )


class Member(Base):
    """Plan members / employees."""
    __tablename__ = "member"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    group_id = Column(PG_UUID(as_uuid=True), ForeignKey("employer_group.id"), nullable=False)
    name = Column(String(255), nullable=False)
    enrollment_start = Column(Date(), nullable=False)
    enrollment_end = Column(Date(), nullable=True)

    # Relationships
    group = relationship("EmployerGroup", back_populates="members")
    claims = relationship("Claim", back_populates="member")

    __table_args__ = (
        Index("ix_member_group_id", "group_id"),
        Index("ix_member_enrollment_start", "enrollment_start"),
        Index("ix_member_enrollment_end", "enrollment_end"),
    )


class BankAccount(Base):
    """Bank accounts (clearing, operating, etc.)."""
    __tablename__ = "bank_account"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False, unique=True)
    type = Column(_ev(BankAccountType), nullable=False)
    institution = Column(String(255), nullable=False)

    # Relationships
    ledger_entries = relationship("LedgerEntry", back_populates="bank_account")
    bank_events = relationship("BankEvent", back_populates="bank_account")
    payment_batches = relationship("PaymentBatch", back_populates="bank_account")


class Claim(Base):
    """Health insurance claims."""
    __tablename__ = "claim"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    group_id = Column(PG_UUID(as_uuid=True), ForeignKey("employer_group.id"), nullable=False)
    member_id = Column(PG_UUID(as_uuid=True), ForeignKey("member.id"), nullable=False)
    provider_name = Column(String(255), nullable=False)
    claim_date = Column(Date(), nullable=False)
    paid_date = Column(Date(), nullable=True)
    billed_amount = Column(Numeric(12, 2), nullable=False)
    allowed_amount = Column(Numeric(12, 2), nullable=False)
    paid_amount = Column(Numeric(12, 2), nullable=False)
    status = Column(_ev(ClaimStatus), nullable=False, default=ClaimStatus.PENDING)
    payment_batch_id = Column(PG_UUID(as_uuid=True), ForeignKey("payment_batch.id"), nullable=True)

    # Relationships
    group = relationship("EmployerGroup", back_populates="claims")
    member = relationship("Member", back_populates="claims")
    payment_batch = relationship("PaymentBatch", back_populates="claims")

    __table_args__ = (
        Index("ix_claim_group_id", "group_id"),
        Index("ix_claim_member_id", "member_id"),
        Index("ix_claim_payment_batch_id", "payment_batch_id"),
        Index("ix_claim_status", "status"),
    )


class PaymentBatch(Base):
    """ACH/batch payment from clearing account."""
    __tablename__ = "payment_batch"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    batch_date = Column(Date(), nullable=False)
    bank_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=False)
    total_amount = Column(Numeric(12, 2), nullable=False)

    # Relationships
    bank_account = relationship("BankAccount", back_populates="payment_batches")
    claims = relationship("Claim", back_populates="payment_batch")

    __table_args__ = (
        Index("ix_payment_batch_batch_date", "batch_date"),
        Index("ix_payment_batch_bank_account_id", "bank_account_id"),
    )


class LedgerEntry(Base):
    """Book entries (expected money movements)."""
    __tablename__ = "ledger_entry"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    group_id = Column(PG_UUID(as_uuid=True), ForeignKey("employer_group.id"), nullable=True)
    bank_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=False)
    entry_type = Column(_ev(LedgerEntryType), nullable=False)
    direction = Column(_ev(Direction), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    expected_date = Column(Date(), nullable=False)
    reference = Column(String(255), nullable=True)
    counterparty = Column(String(255), nullable=True)
    source_artifact = Column(String(255), nullable=True)
    status = Column(_ev(LedgerEntryStatus), nullable=False, default=LedgerEntryStatus.EXPECTED)

    # Relationships
    group = relationship("EmployerGroup", back_populates="ledger_entries")
    bank_account = relationship("BankAccount", back_populates="ledger_entries")

    __table_args__ = (
        Index("ix_ledger_entry_group_id", "group_id"),
        Index("ix_ledger_entry_bank_account_id", "bank_account_id"),
        Index("ix_ledger_entry_expected_date", "expected_date"),
        Index("ix_ledger_entry_status", "status"),
    )


class BankEvent(Base):
    """Actual bank postings (bank statement records)."""
    __tablename__ = "bank_event"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    bank_account_id = Column(PG_UUID(as_uuid=True), ForeignKey("bank_account.id"), nullable=False)
    posted_date = Column(Date(), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    direction = Column(_ev(Direction), nullable=False)
    descriptor = Column(String(255), nullable=False)
    bank_reference = Column(String(255), nullable=True)

    # Relationships
    bank_account = relationship("BankAccount", back_populates="bank_events")

    __table_args__ = (
        Index("ix_bank_event_bank_account_id", "bank_account_id"),
        Index("ix_bank_event_posted_date", "posted_date"),
    )


class GroundTruthLink(Base):
    """
    Ground truth mapping for evaluation.

    Seed writes bank_reference (natural key for bank_event) and ledger_natural_ref
    (natural key for ledger_entry — claim_id for 835 rows, invoice ref for 820 rows).
    After ingest + finalize, bank_event_id and ledger_entry_id are resolved from those keys.

    bank_only_noise rows: ledger_natural_ref = NULL, ledger_entry_id stays NULL.
    No FK constraints — both UUID columns start NULL and are resolved by finalize.
    """
    __tablename__ = "ground_truth_link"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    bank_reference = Column(String(255), nullable=False)
    ledger_natural_ref = Column(String(255), nullable=True)
    exception_type = Column(_ev(ExceptionType), nullable=False)
    bank_event_id = Column(PG_UUID(as_uuid=True), nullable=True)    # resolved by finalize; no FK
    ledger_entry_id = Column(PG_UUID(as_uuid=True), nullable=True)  # resolved by finalize; no FK
    created_at = Column(DateTime(), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ground_truth_link_bank_event_id", "bank_event_id"),
        Index("ix_ground_truth_link_ledger_entry_id", "ledger_entry_id"),
        Index("ix_ground_truth_link_exception_type", "exception_type"),
        Index("ix_ground_truth_link_bank_reference", "bank_reference"),
    )


class ReconciliationMatch(Base):
    """
    Reconciliation matches (empty until Step 2).
    Created by the matching engine; initially empty.
    """
    __tablename__ = "reconciliation_match"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    bank_event_id = Column(PG_UUID(as_uuid=True), ForeignKey("bank_event.id"), nullable=False)
    match_type = Column(String(255), nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    status = Column(_ev(ReconciliationMatchStatus), nullable=False, default=ReconciliationMatchStatus.PENDING)
    resolved_by = Column(String(255), nullable=True)
    resolved_at = Column(DateTime(), nullable=True)
    notes = Column(String(1024), nullable=True)

    __table_args__ = (
        Index("ix_reconciliation_match_bank_event_id", "bank_event_id"),
        Index("ix_reconciliation_match_status", "status"),
    )


class MatchLedgerEntry(Base):
    """
    Join table: reconciliation_match <-> ledger_entry (many-to-many).
    A match can cover one or more ledger entries.
    """
    __tablename__ = "match_ledger_entry"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    reconciliation_match_id = Column(PG_UUID(as_uuid=True), ForeignKey("reconciliation_match.id"), nullable=False)
    ledger_entry_id = Column(PG_UUID(as_uuid=True), ForeignKey("ledger_entry.id"), nullable=False)
    allocated_amount = Column(Numeric(12, 2), nullable=True)  # set by split action; NULL = full assignment

    __table_args__ = (
        Index("ix_match_ledger_entry_match_id", "reconciliation_match_id"),
        Index("ix_match_ledger_entry_ledger_entry_id", "ledger_entry_id"),
    )


class AuditLog(Base):
    """Audit trail for data changes."""
    __tablename__ = "audit_log"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    actor = Column(String(255), nullable=False)
    action = Column(String(255), nullable=False)
    entity_type = Column(String(255), nullable=False)
    entity_id = Column(PG_UUID(as_uuid=True), nullable=True)
    payload = Column(JSONB(), nullable=True)
    created_at = Column(DateTime(), nullable=False, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_entity_type_entity_id", "entity_type", "entity_id"),
    )
