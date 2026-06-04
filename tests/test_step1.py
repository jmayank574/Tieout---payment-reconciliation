"""
Pytest test suite for Tieout Step 1.
Tests money conservation, ground truth completeness, and reproducibility.
Run with: pytest tests/ -v
"""

import pytest
from decimal import Decimal
from sqlalchemy import func

from backend.db.connection import SessionLocal, drop_db, init_db
from backend.db.models import (
    EmployerGroup, Claim, ClaimStatus, PaymentBatch,
    LedgerEntry, LedgerEntryType, BankEvent, GroundTruthLink,
    Direction, ExceptionType,
)
from backend.seed.generator import generate_synthetic_data
from backend.ingest.pipeline import run_ingest
from backend.config import SEED


@pytest.fixture(scope="module")
def seeded_db():
    """Seed + ingest once per module; tests share the fully-populated DB state."""
    drop_db()
    init_db()
    generate_synthetic_data(seed=SEED)
    run_ingest()
    yield
    # Leave DB intact after tests so summary / DBeaver queries still work.


class TestMoneyConservation:
    """Money is conserved across the system."""

    def test_batch_totals_equal_sum_of_claims(self, seeded_db):
        """Each payment_batch total must equal the sum of its claims' paid_amounts."""
        session = SessionLocal()
        try:
            batches = session.query(PaymentBatch).all()
            assert len(batches) > 0, "No batches found"

            for batch in batches:
                claim_sum = (
                    session.query(func.sum(Claim.paid_amount))
                    .filter(Claim.payment_batch_id == batch.id)
                    .scalar() or Decimal(0)
                )
                assert Decimal(str(batch.total_amount)) == claim_sum, (
                    f"Batch {batch.id}: total={batch.total_amount}, claim_sum={claim_sum}"
                )
        finally:
            session.close()

    def test_ledger_has_both_debits_and_credits(self, seeded_db):
        """Ledger must contain non-zero debits and credits."""
        session = SessionLocal()
        try:
            debits = (
                session.query(func.sum(LedgerEntry.amount))
                .filter(LedgerEntry.direction == Direction.DEBIT)
                .scalar() or Decimal(0)
            )
            credits = (
                session.query(func.sum(LedgerEntry.amount))
                .filter(LedgerEntry.direction == Direction.CREDIT)
                .scalar() or Decimal(0)
            )
            assert debits > 0, "No ledger debits found"
            assert credits > 0, "No ledger credits found"
        finally:
            session.close()


class TestGroundTruthCompleteness:
    """ground_truth_link covers all bank events correctly."""

    def test_every_bank_event_has_at_least_one_link(self, seeded_db):
        """Every bank_event must have at least one ground_truth_link."""
        session = SessionLocal()
        try:
            unlinked = (
                session.query(BankEvent)
                .filter(
                    ~BankEvent.id.in_(
                        session.query(GroundTruthLink.bank_event_id).distinct()
                    )
                )
                .count()
            )
            assert unlinked == 0, f"{unlinked} bank events have no ground_truth_link"
        finally:
            session.close()

    def test_bank_only_noise_has_null_ledger_entry(self, seeded_db):
        """bank_only_noise links must have NULL ledger_entry_id."""
        session = SessionLocal()
        try:
            bad = (
                session.query(GroundTruthLink)
                .filter(
                    GroundTruthLink.exception_type == ExceptionType.BANK_ONLY_NOISE,
                    GroundTruthLink.ledger_entry_id.isnot(None),
                )
                .count()
            )
            assert bad == 0, f"{bad} bank_only_noise entries have ledger_entry_id set"
        finally:
            session.close()

    def test_non_noise_links_have_ledger_entry(self, seeded_db):
        """All non-bank_only_noise links must have ledger_entry_id set."""
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
            assert bad == 0, f"{bad} non-noise links have NULL ledger_entry_id"
        finally:
            session.close()

    def test_paid_claim_count_equals_claim_payment_entries(self, seeded_db):
        """Every PAID claim must have exactly one claim_payment ledger entry."""
        session = SessionLocal()
        try:
            paid_claims = session.query(Claim).filter(Claim.status == ClaimStatus.PAID).count()
            claim_payment_entries = (
                session.query(LedgerEntry)
                .filter(LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT)
                .count()
            )
            assert paid_claims == claim_payment_entries, (
                f"paid_claims={paid_claims} != claim_payment_entries={claim_payment_entries}"
            )
        finally:
            session.close()

    def test_all_exception_types_present(self, seeded_db):
        """Every exception type must appear at least once in ground_truth_link."""
        session = SessionLocal()
        try:
            for exc in ExceptionType:
                count = (
                    session.query(GroundTruthLink)
                    .filter(GroundTruthLink.exception_type == exc)
                    .count()
                )
                assert count > 0, f"Exception type '{exc.value}' has 0 ground_truth_links"
        finally:
            session.close()


class TestReproducibility:
    """Same seed produces identical data across two full seed+ingest runs."""

    def test_same_seed_same_row_counts(self):
        """Two seed+ingest runs with seed=42 produce the same structural counts."""
        drop_db(); init_db()
        r1 = generate_synthetic_data(seed=42)
        run_ingest()

        drop_db(); init_db()
        r2 = generate_synthetic_data(seed=42)
        run_ingest()

        # Check structural (seed-written) objects
        for entity in ("groups", "members", "accounts", "claims", "batches",
                       "ground_truth_links", "records_835", "records_820", "bank_records"):
            assert len(r1[entity]) == len(r2[entity]), (
                f"{entity}: run1={len(r1[entity])}, run2={len(r2[entity])}"
            )

    def test_same_seed_same_dollar_totals(self):
        """Two seed+ingest runs with seed=42 produce identical ledger dollar totals."""
        drop_db(); init_db()
        generate_synthetic_data(seed=42)
        run_ingest()
        s1 = SessionLocal()
        d1 = s1.query(func.sum(LedgerEntry.amount)).filter(LedgerEntry.direction == Direction.DEBIT).scalar()
        c1 = s1.query(func.sum(LedgerEntry.amount)).filter(LedgerEntry.direction == Direction.CREDIT).scalar()
        s1.close()

        drop_db(); init_db()
        generate_synthetic_data(seed=42)
        run_ingest()
        s2 = SessionLocal()
        d2 = s2.query(func.sum(LedgerEntry.amount)).filter(LedgerEntry.direction == Direction.DEBIT).scalar()
        c2 = s2.query(func.sum(LedgerEntry.amount)).filter(LedgerEntry.direction == Direction.CREDIT).scalar()
        s2.close()

        assert d1 == d2, f"Debit totals differ: {d1} vs {d2}"
        assert c1 == c2, f"Credit totals differ: {c1} vs {c2}"
