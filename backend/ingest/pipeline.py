"""
Ingest pipeline: parse artifacts → normalize → write → finalize ground_truth_link.

Run order:
  1. Parse 835, 820, bank CSV from data/raw/
  2. Normalize + deduplicate → write ledger_entry and bank_event with fresh UUIDs
  3. Finalize: UPDATE ground_truth_link SET bank_event_id / ledger_entry_id
     by joining on natural refs (bank_reference, ledger_natural_ref)
  4. Round-trip check: compare ingested counts/totals against claim table
  5. Write audit_log entry
"""

from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.config import DATA_DIR
from backend.db.connection import SessionLocal
from backend.db.models import (
    AuditLog, BankEvent, Claim, ClaimStatus,
    LedgerEntry, LedgerEntryType, PaymentBatch,
)
from backend.ingest.normalizer import normalize_835, normalize_820, normalize_bank
from backend.ingest.parsers.parser_835 import parse_835
from backend.ingest.parsers.parser_820 import parse_820
from backend.ingest.parsers.parser_bank import parse_bank

log = logging.getLogger(__name__)


def run_ingest(data_dir: Path | None = None) -> dict:
    """
    Parse artifact files, write canonical rows, finalize ground truth links.
    Returns a stats dict.  Raises on round-trip mismatch.
    """
    if data_dir is None:
        data_dir = Path(DATA_DIR) / "raw"

    session = SessionLocal()
    try:
        rows_835 = parse_835(data_dir / "835_remittance.json")
        rows_820 = parse_820(data_dir / "820_premium.json")
        rows_bank = parse_bank(data_dir / "bank_transactions.csv")

        le_835 = normalize_835(rows_835, session)
        le_820 = normalize_820(rows_820, session)
        be = normalize_bank(rows_bank, session)
        session.flush()

        _finalize_ground_truth_links(session)
        roundtrip = _check_roundtrip(session)

        session.add(AuditLog(
            actor="ingest_pipeline",
            action="ingest_run",
            entity_type="pipeline",
            payload={
                "parsed_835": len(rows_835),
                "parsed_820": len(rows_820),
                "parsed_bank": len(rows_bank),
                "written_ledger_835": len(le_835),
                "written_ledger_820": len(le_820),
                "written_bank_events": len(be),
                "roundtrip": roundtrip,
            },
        ))
        session.commit()

        stats = {
            "parsed_835": len(rows_835),
            "parsed_820": len(rows_820),
            "parsed_bank": len(rows_bank),
            "written_ledger_835": len(le_835),
            "written_ledger_820": len(le_820),
            "written_bank_events": len(be),
            "roundtrip": roundtrip,
        }
        return stats

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _finalize_ground_truth_links(session: Session) -> None:
    """Resolve natural refs in ground_truth_link to freshly-minted UUIDs."""
    session.execute(text("""
        UPDATE ground_truth_link gtl
        SET bank_event_id = be.id
        FROM bank_event be
        WHERE be.bank_reference = gtl.bank_reference
          AND gtl.bank_event_id IS NULL
    """))
    session.execute(text("""
        UPDATE ground_truth_link gtl
        SET ledger_entry_id = le.id
        FROM ledger_entry le
        WHERE le.reference = gtl.ledger_natural_ref
          AND gtl.ledger_natural_ref IS NOT NULL
          AND gtl.ledger_entry_id IS NULL
    """))
    session.flush()


def _check_roundtrip(session: Session) -> dict:
    """Compare ingested ledger rows against source-of-truth business entity tables."""
    paid_count = (
        session.query(func.count(Claim.id))
        .filter(Claim.status == ClaimStatus.PAID)
        .scalar() or 0
    )
    paid_total: Decimal = (
        session.query(func.sum(Claim.paid_amount))
        .filter(Claim.status == ClaimStatus.PAID)
        .scalar() or Decimal(0)
    )
    le_count = (
        session.query(func.count(LedgerEntry.id))
        .filter(LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT)
        .scalar() or 0
    )
    le_total: Decimal = (
        session.query(func.sum(LedgerEntry.amount))
        .filter(LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT)
        .scalar() or Decimal(0)
    )
    batch_total: Decimal = (
        session.query(func.sum(PaymentBatch.total_amount)).scalar() or Decimal(0)
    )

    count_ok = paid_count == le_count
    total_ok = paid_total == le_total
    batch_ok = batch_total == le_total

    if not count_ok:
        raise ValueError(
            f"Round-trip count mismatch: paid_claims={paid_count}, claim_payment_entries={le_count}"
        )
    if not total_ok:
        raise ValueError(
            f"Round-trip total mismatch: paid_total={paid_total}, le_total={le_total}"
        )
    if not batch_ok:
        log.warning(
            "Batch total (%s) != claim_payment ledger total (%s) — "
            "possible rounding in short_over_funding entries",
            batch_total, le_total,
        )

    return {
        "paid_claims": paid_count,
        "paid_total": str(paid_total),
        "ingested_claim_payments": le_count,
        "ingested_total": str(le_total),
        "batch_total": str(batch_total),
        "count_ok": count_ok,
        "total_ok": total_ok,
        "batch_le_ok": batch_ok,
    }
