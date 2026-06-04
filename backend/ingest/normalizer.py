"""
Normalizer: parsed artifact rows → ORM objects with ingest-minted UUIDs.

Dedup rules (idempotent re-ingest):
  - LedgerEntry: deduplicated by ledger_entry.reference
      835 → reference = claim_id
      820 → reference = row_ref
  - BankEvent: deduplicated by bank_event.bank_reference
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from backend.db.models import (
    BankEvent, Direction,
    LedgerEntry, LedgerEntryStatus, LedgerEntryType,
)
from backend.ingest.schemas import Raw835Row, Raw820Row, RawBankRow

_ENTRY_TYPE_MAP = {
    "employer_funding": LedgerEntryType.EMPLOYER_FUNDING,
    "claim_payment": LedgerEntryType.CLAIM_PAYMENT,
    "admin_fee": LedgerEntryType.ADMIN_FEE,
    "stop_loss_premium": LedgerEntryType.STOP_LOSS_PREMIUM,
    "stop_loss_reimbursement": LedgerEntryType.STOP_LOSS_REIMBURSEMENT,
}

_DIRECTION_MAP = {
    "debit": Direction.DEBIT,
    "credit": Direction.CREDIT,
}


def normalize_835(rows: list[Raw835Row], session: Session) -> list[LedgerEntry]:
    """Create ledger_entry rows for 835 claim-payment records. Dedup by reference."""
    existing = {
        r[0] for r in session.query(LedgerEntry.reference)
        .filter(LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT)
        .all()
    }
    entries: list[LedgerEntry] = []
    for row in rows:
        if row.claim_id in existing:
            continue
        entry = LedgerEntry(
            id=uuid4(),
            group_id=row.group_id,
            bank_account_id=row.bank_account_id,
            entry_type=LedgerEntryType.CLAIM_PAYMENT,
            direction=Direction.DEBIT,
            amount=row.paid_amount,
            expected_date=row.paid_date,
            reference=row.claim_id,
            counterparty=row.provider_name,
            source_artifact="835",
            status=LedgerEntryStatus.EXPECTED,
        )
        session.add(entry)
        entries.append(entry)
        existing.add(row.claim_id)
    return entries


def normalize_820(rows: list[Raw820Row], session: Session) -> list[LedgerEntry]:
    """Create ledger_entry rows for 820 records (funding, fees, stop-loss). Dedup by reference."""
    existing = {
        r[0] for r in session.query(LedgerEntry.reference)
        .filter(LedgerEntry.entry_type != LedgerEntryType.CLAIM_PAYMENT)
        .all()
    }
    entries: list[LedgerEntry] = []
    for row in rows:
        if row.row_ref in existing:
            continue
        entry_type = _ENTRY_TYPE_MAP.get(row.entry_type)
        if entry_type is None:
            continue
        direction = _DIRECTION_MAP.get(row.direction)
        if direction is None:
            continue
        entry = LedgerEntry(
            id=uuid4(),
            group_id=row.group_id,
            bank_account_id=row.bank_account_id,
            entry_type=entry_type,
            direction=direction,
            amount=row.amount,
            expected_date=row.expected_date,
            reference=row.row_ref,
            counterparty=row.counterparty,
            source_artifact=row.source_artifact,
            status=LedgerEntryStatus.EXPECTED,
        )
        session.add(entry)
        entries.append(entry)
        existing.add(row.row_ref)
    return entries


def normalize_bank(rows: list[RawBankRow], session: Session) -> list[BankEvent]:
    """Create bank_event rows from bank CSV records. Dedup by bank_reference."""
    existing = {
        r[0] for r in session.query(BankEvent.bank_reference).all()
    }
    events: list[BankEvent] = []
    for row in rows:
        if row.bank_reference in existing:
            continue
        direction = _DIRECTION_MAP.get(row.direction)
        if direction is None:
            continue
        event = BankEvent(
            id=uuid4(),
            bank_account_id=row.bank_account_id,
            posted_date=row.posted_date,
            amount=row.amount,
            direction=direction,
            descriptor=row.descriptor,
            bank_reference=row.bank_reference,
        )
        session.add(event)
        events.append(event)
        existing.add(row.bank_reference)
    return events
