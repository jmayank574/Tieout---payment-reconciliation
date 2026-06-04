"""
Pytest test suite for Tieout Step 2 — ingest and normalization layer.

Tests: parser happy paths, malformed-row skipping, idempotent re-ingest,
       round-trip claim counts and dollar totals, ground_truth_link resolution.
"""

import json
import shutil
import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func

from backend.config import DATA_DIR, SEED
from backend.db.connection import SessionLocal, drop_db, init_db
from backend.db.models import (
    BankEvent, Claim, ClaimStatus,
    GroundTruthLink, ExceptionType,
    LedgerEntry, LedgerEntryType,
)
from backend.ingest.parsers.parser_835 import parse_835
from backend.ingest.parsers.parser_820 import parse_820
from backend.ingest.parsers.parser_bank import parse_bank
from backend.ingest.pipeline import run_ingest
from backend.seed.generator import generate_synthetic_data


@pytest.fixture(scope="module")
def seeded_and_ingested():
    """Full seed + ingest run shared by all Step 2 tests."""
    drop_db()
    init_db()
    generate_synthetic_data(seed=SEED)
    run_ingest()
    yield


RAW_DIR = Path(DATA_DIR) / "raw"


# ─────────────────────────────────────────────────────────────────────────────
# Parser happy paths
# ─────────────────────────────────────────────────────────────────────────────

class TestParsers:
    def test_parser_835_row_count_matches_paid_claims(self, seeded_and_ingested):
        """Parser must return exactly one row per paid claim."""
        rows = parse_835(RAW_DIR / "835_remittance.json")
        session = SessionLocal()
        try:
            paid = session.query(func.count(Claim.id)).filter(Claim.status == ClaimStatus.PAID).scalar()
        finally:
            session.close()
        assert len(rows) == paid, f"835 rows={len(rows)}, paid_claims={paid}"

    def test_parser_820_all_rows_have_row_ref(self, seeded_and_ingested):
        """Every 820 row must have a non-empty row_ref (natural key)."""
        rows = parse_820(RAW_DIR / "820_premium.json")
        assert len(rows) > 0, "No 820 rows parsed"
        for row in rows:
            assert row.row_ref, f"Empty row_ref in row: {row}"

    def test_parser_bank_row_count_matches_bank_events(self, seeded_and_ingested):
        """Parser must return exactly one row per bank_event in the DB."""
        rows = parse_bank(RAW_DIR / "bank_transactions.csv")
        session = SessionLocal()
        try:
            be_count = session.query(func.count(BankEvent.id)).scalar()
        finally:
            session.close()
        assert len(rows) == be_count, f"bank rows={len(rows)}, bank_events={be_count}"


# ─────────────────────────────────────────────────────────────────────────────
# Malformed row skipping
# ─────────────────────────────────────────────────────────────────────────────

class TestMalformedRows:
    def test_malformed_835_row_is_skipped(self, seeded_and_ingested):
        """A 835 row missing paid_amount must be skipped; valid rows still parse."""
        raw = json.loads((RAW_DIR / "835_remittance.json").read_text(encoding="utf-8"))
        good_count = len(raw["transactions"])

        # Inject one bad row (missing paid_amount)
        bad_tx = {
            "claim_id": "00000000-0000-0000-0000-000000000099",
            "group_id": "00000000-0000-0000-0000-000000000001",
            "payment_batch_id": "00000000-0000-0000-0000-000000000002",
            "provider_name": "Bad Provider",
            # paid_amount intentionally missing
            "paid_date": "2026-01-01",
            "bank_account_id": "00000000-0000-0000-0000-000000000003",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "835_remittance.json"
            injected = dict(raw)
            injected["transactions"] = raw["transactions"] + [bad_tx]
            tmp_path.write_text(json.dumps(injected), encoding="utf-8")

            rows = parse_835(tmp_path)
            assert len(rows) == good_count, (
                f"Expected {good_count} valid rows (bad row should be skipped), got {len(rows)}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Idempotency
# ─────────────────────────────────────────────────────────────────────────────

class TestIdempotency:
    def test_reingest_does_not_create_duplicates(self, seeded_and_ingested):
        """Running ingest twice must not change ledger_entry or bank_event counts."""
        session = SessionLocal()
        try:
            le_before = session.query(func.count(LedgerEntry.id)).scalar()
            be_before = session.query(func.count(BankEvent.id)).scalar()
        finally:
            session.close()

        run_ingest()  # second run

        session = SessionLocal()
        try:
            le_after = session.query(func.count(LedgerEntry.id)).scalar()
            be_after = session.query(func.count(BankEvent.id)).scalar()
        finally:
            session.close()

        assert le_after == le_before, f"ledger_entry duplicated: {le_before} -> {le_after}"
        assert be_after == be_before, f"bank_event duplicated: {be_before} -> {be_after}"


# ─────────────────────────────────────────────────────────────────────────────
# Round-trip checks (independent from ground_truth.json)
# ─────────────────────────────────────────────────────────────────────────────

class TestRoundTrip:
    def test_claim_payment_count_equals_paid_claims(self, seeded_and_ingested):
        """Ingested claim_payment entries must equal paid claim count in claim table."""
        session = SessionLocal()
        try:
            paid = session.query(func.count(Claim.id)).filter(Claim.status == ClaimStatus.PAID).scalar()
            le = session.query(func.count(LedgerEntry.id)).filter(
                LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT
            ).scalar()
            assert paid == le, f"paid_claims={paid}, claim_payment_entries={le}"
        finally:
            session.close()

    def test_claim_payment_total_equals_paid_claim_sum(self, seeded_and_ingested):
        """SUM(ledger_entry.amount WHERE type=claim_payment) must equal SUM(claim.paid_amount WHERE status=paid)."""
        session = SessionLocal()
        try:
            paid_total = (
                session.query(func.sum(Claim.paid_amount))
                .filter(Claim.status == ClaimStatus.PAID)
                .scalar() or Decimal(0)
            )
            le_total = (
                session.query(func.sum(LedgerEntry.amount))
                .filter(LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT)
                .scalar() or Decimal(0)
            )
            assert paid_total == le_total, f"paid_total={paid_total}, le_total={le_total}"
        finally:
            session.close()


# ─────────────────────────────────────────────────────────────────────────────
# Ground truth link resolution
# ─────────────────────────────────────────────────────────────────────────────

class TestGroundTruthResolution:
    def test_all_non_noise_links_resolved(self, seeded_and_ingested):
        """After finalize, every non-noise ground_truth_link must have bank_event_id set."""
        session = SessionLocal()
        try:
            unresolved = (
                session.query(GroundTruthLink)
                .filter(
                    GroundTruthLink.bank_event_id.is_(None),
                )
                .count()
            )
            assert unresolved == 0, f"{unresolved} ground_truth_link rows still have NULL bank_event_id"
        finally:
            session.close()

    def test_non_noise_links_have_ledger_entry_id(self, seeded_and_ingested):
        """After finalize, non-bank_only_noise links must have ledger_entry_id set."""
        session = SessionLocal()
        try:
            bad = (
                session.query(GroundTruthLink)
                .filter(
                    GroundTruthLink.exception_type != ExceptionType.BANK_ONLY_NOISE,
                    GroundTruthLink.ledger_entry_id.is_(None),
                )
                .count()
            )
            assert bad == 0, f"{bad} non-noise links still have NULL ledger_entry_id after finalize"
        finally:
            session.close()
