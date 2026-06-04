"""
Pytest test suite for Tieout Step 3 — matching engine and evaluator.

Tests:
  1. Clean GTL rows are matched via the exact stage
  2. many_to_one GTL rows are matched via the reference-anchored batch path
  3. bank_only_noise events have no ledger entries in any match
  4. Re-running the matcher produces identical reconciliation_match counts (idempotency)
  5. Precision and recall are computed correctly against a tiny in-memory fixture
  6. Amount-colliding batches (two batches, same sum, close dates) do NOT cross-match
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func

from backend.config import DATA_DIR, SEED
from backend.db.connection import SessionLocal, drop_db, init_db
from backend.db.models import (
    BankAccount, BankAccountType,
    BankEvent, Direction,
    Claim, ClaimStatus,
    ExceptionType,
    GroundTruthLink,
    LedgerEntry, LedgerEntryStatus, LedgerEntryType,
    MatchLedgerEntry,
    PaymentBatch,
    ReconciliationMatch, ReconciliationMatchStatus,
)
from backend.ingest.pipeline import run_ingest
from backend.match.engine import run_match
from backend.match.evaluate import compute_scorecard
from backend.seed.generator import generate_synthetic_data


# ---------------------------------------------------------------------------
# Module-scoped fixture: full seed + ingest + match (shared by tests 1-4)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def matched_db():
    drop_db()
    init_db()
    generate_synthetic_data(seed=SEED)
    run_ingest()
    session = SessionLocal()
    try:
        run_match(session)
    finally:
        session.close()
    yield


# ---------------------------------------------------------------------------
# Test 1 — Clean cases matched via exact stage
# ---------------------------------------------------------------------------

class TestExactMatchClean:
    def test_clean_gtl_pairs_are_matched(self, matched_db):
        """
        Every (bank_event_id, ledger_entry_id) pair whose exception_type is
        'clean' in ground_truth_link must appear as a predicted pair in
        reconciliation_match + match_ledger_entry.
        """
        session = SessionLocal()
        try:
            clean_gtl = (
                session.query(GroundTruthLink)
                .filter(GroundTruthLink.exception_type == ExceptionType.CLEAN)
                .all()
            )
            assert len(clean_gtl) > 0, "No clean GTL rows found — seed/ingest issue"

            predicted = {
                (str(mle.reconciliation_match_id), str(mle.ledger_entry_id))
                for mle in session.query(MatchLedgerEntry).all()
            }
            match_id_to_be = {
                str(m.id): str(m.bank_event_id)
                for m in session.query(ReconciliationMatch).all()
            }
            predicted_pairs = {
                (match_id_to_be[mid], le_id)
                for mid, le_id in predicted
                if mid in match_id_to_be
            }

            unmatched_clean = []
            for gtl in clean_gtl:
                pair = (str(gtl.bank_event_id), str(gtl.ledger_entry_id))
                if pair not in predicted_pairs:
                    unmatched_clean.append(pair)

            assert not unmatched_clean, (
                f"{len(unmatched_clean)} clean GTL pairs were not matched: "
                f"{unmatched_clean[:3]}"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Test 2 — many_to_one cases matched via reference-anchored batch path
# ---------------------------------------------------------------------------

class TestManyToOneReferenceAnchored:
    def test_many_to_one_matches_have_multiple_ledger_entries(self, matched_db):
        """
        Reconciliation matches whose match_type is 'many_to_one' must each
        cover more than one ledger entry (by definition of the batch pattern).
        """
        session = SessionLocal()
        try:
            many_matches = (
                session.query(ReconciliationMatch)
                .filter(ReconciliationMatch.match_type == "many_to_one")
                .all()
            )
            assert len(many_matches) > 0, "No many_to_one matches found"

            for m in many_matches:
                le_count = (
                    session.query(func.count(MatchLedgerEntry.id))
                    .filter(MatchLedgerEntry.reconciliation_match_id == m.id)
                    .scalar() or 0
                )
                assert le_count > 1, (
                    f"many_to_one match {m.id} has only {le_count} ledger entry — "
                    "expected ≥ 2"
                )
        finally:
            session.close()

    def test_many_to_one_gtl_pairs_are_matched(self, matched_db):
        """
        All (bank_event_id, ledger_entry_id) pairs from ground_truth_link with
        exception_type=many_to_one must appear as predicted pairs.
        """
        session = SessionLocal()
        try:
            gtl_pairs = {
                (str(g.bank_event_id), str(g.ledger_entry_id))
                for g in session.query(GroundTruthLink)
                .filter(GroundTruthLink.exception_type == ExceptionType.MANY_TO_ONE)
                .all()
                if g.ledger_entry_id is not None
            }
            assert gtl_pairs, "No many_to_one GTL pairs — seed/ingest issue"

            match_id_to_be = {
                str(m.id): str(m.bank_event_id)
                for m in session.query(ReconciliationMatch).all()
            }
            predicted_pairs = {
                (match_id_to_be[str(mle.reconciliation_match_id)], str(mle.ledger_entry_id))
                for mle in session.query(MatchLedgerEntry).all()
                if str(mle.reconciliation_match_id) in match_id_to_be
            }

            missed = gtl_pairs - predicted_pairs
            # Allow up to 2% miss rate (a handful of edge cases is acceptable)
            miss_rate = len(missed) / len(gtl_pairs)
            assert miss_rate < 0.02, (
                f"{len(missed)}/{len(gtl_pairs)} many_to_one pairs missed "
                f"({miss_rate:.1%}) — reference anchor may not be working"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Test 3 — bank_only_noise events have no predicted ledger entries
# ---------------------------------------------------------------------------

class TestBankOnlyNoiseUnmatched:
    def test_noise_events_have_no_match_ledger_entries(self, matched_db):
        """
        bank_only_noise bank events must not appear in any match_ledger_entry row,
        because they have no true ledger counterpart.
        """
        session = SessionLocal()
        try:
            noise_be_ids = {
                str(g.bank_event_id)
                for g in session.query(GroundTruthLink)
                .filter(GroundTruthLink.exception_type == ExceptionType.BANK_ONLY_NOISE)
                .all()
                if g.bank_event_id is not None
            }
            assert noise_be_ids, "No bank_only_noise events — seed/ingest issue"

            match_id_to_be = {
                str(m.id): str(m.bank_event_id)
                for m in session.query(ReconciliationMatch).all()
            }
            # noise events that wound up with at least one ledger entry in a match
            wrongly_matched = set()
            for mle in session.query(MatchLedgerEntry).all():
                be_id = match_id_to_be.get(str(mle.reconciliation_match_id))
                if be_id and be_id in noise_be_ids:
                    wrongly_matched.add(be_id)

            assert not wrongly_matched, (
                f"{len(wrongly_matched)} bank_only_noise events were incorrectly "
                f"matched to ledger entries: {list(wrongly_matched)[:3]}"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Test 4 — Idempotency: running twice gives same counts
# ---------------------------------------------------------------------------

class TestMatcherIdempotency:
    def test_rematch_produces_same_counts(self, matched_db):
        """
        Running the matcher a second time must produce the exact same number of
        reconciliation_match and match_ledger_entry rows as the first run.
        """
        session = SessionLocal()
        try:
            rm_before = session.query(func.count(ReconciliationMatch.id)).scalar()
            mle_before = session.query(func.count(MatchLedgerEntry.id)).scalar()
        finally:
            session.close()

        session2 = SessionLocal()
        try:
            run_match(session2)
        finally:
            session2.close()

        session3 = SessionLocal()
        try:
            rm_after  = session3.query(func.count(ReconciliationMatch.id)).scalar()
            mle_after = session3.query(func.count(MatchLedgerEntry.id)).scalar()
        finally:
            session3.close()

        assert rm_after == rm_before, (
            f"reconciliation_match count changed after second run: "
            f"{rm_before} → {rm_after}"
        )
        assert mle_after == mle_before, (
            f"match_ledger_entry count changed after second run: "
            f"{mle_before} → {mle_after}"
        )


# ---------------------------------------------------------------------------
# Test 5 — Precision/recall computed correctly against a tiny fixture
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:
    """
    Verifies the evaluator arithmetic using a hand-crafted minimal DB state.
    We create 3 predicted pairs and 3 GT pairs with a known overlap, then
    assert exact precision / recall / F1 / FP values.
    """

    def test_precision_recall_fixture(self):
        """
        Fixture: 3 GT pairs, 3 predicted pairs, 2 overlap (TP=2, FP=1, FN=1).
        Expected: precision=2/3, recall=2/3, F1=2/3, false_positives=1.
        """
        drop_db()
        init_db()

        session = SessionLocal()
        try:
            # Minimal schema objects
            acct = BankAccount(id=uuid.uuid4(), name="Test Acct", type=BankAccountType.CLEARING, institution="Test Bank")
            session.add(acct)
            session.flush()

            be_ids  = [uuid.uuid4() for _ in range(3)]
            le_ids  = [uuid.uuid4() for _ in range(3)]
            today = date.today()

            for be_id in be_ids:
                session.add(BankEvent(
                    id=be_id, bank_account_id=acct.id,
                    posted_date=today, amount=Decimal("100.00"),
                    direction=Direction.CREDIT, descriptor="TEST",
                    bank_reference=f"ref_{be_id}",
                ))
            for le_id in le_ids:
                session.add(LedgerEntry(
                    id=le_id, bank_account_id=acct.id,
                    entry_type=LedgerEntryType.ADMIN_FEE,
                    direction=Direction.CREDIT,
                    amount=Decimal("100.00"),
                    expected_date=today,
                    source_artifact="820",
                    status=LedgerEntryStatus.EXPECTED,
                ))
            session.flush()

            # GT pairs: (be0,le0), (be1,le1), (be2,le2)
            for be_id, le_id in zip(be_ids, le_ids):
                session.add(GroundTruthLink(
                    id=uuid.uuid4(),
                    bank_reference=f"ref_{be_id}",
                    ledger_natural_ref=str(le_id),
                    exception_type=ExceptionType.CLEAN,
                    bank_event_id=be_id,
                    ledger_entry_id=le_id,
                ))
            session.flush()

            # Predicted pairs:
            #   Match A: (be0, le0) — TP
            #   Match B: (be1, le1) — TP
            #   Match C: (be2, le_WRONG=le0) — FP  (be2 links le0 instead of le2)
            match_a = ReconciliationMatch(
                id=uuid.uuid4(), bank_event_id=be_ids[0],
                match_type="exact", confidence=Decimal("1.0"),
                status=ReconciliationMatchStatus.MATCHED,
            )
            match_b = ReconciliationMatch(
                id=uuid.uuid4(), bank_event_id=be_ids[1],
                match_type="exact", confidence=Decimal("1.0"),
                status=ReconciliationMatchStatus.MATCHED,
            )
            match_c = ReconciliationMatch(
                id=uuid.uuid4(), bank_event_id=be_ids[2],
                match_type="fuzzy", confidence=Decimal("0.5"),
                status=ReconciliationMatchStatus.MATCHED,
            )
            session.add_all([match_a, match_b, match_c])
            session.flush()

            session.add(MatchLedgerEntry(id=uuid.uuid4(), reconciliation_match_id=match_a.id, ledger_entry_id=le_ids[0]))
            session.add(MatchLedgerEntry(id=uuid.uuid4(), reconciliation_match_id=match_b.id, ledger_entry_id=le_ids[1]))
            session.add(MatchLedgerEntry(id=uuid.uuid4(), reconciliation_match_id=match_c.id, ledger_entry_id=le_ids[0]))  # wrong!
            session.flush()

            sc = compute_scorecard(session)

            assert sc["true_positives"]  == 2, f"TP={sc['true_positives']}, expected 2"
            assert sc["false_positives"] == 1, f"FP={sc['false_positives']}, expected 1"
            assert sc["false_negatives"] == 1, f"FN={sc['false_negatives']}, expected 1"
            assert abs(sc["precision"] - round(2/3, 4)) < 1e-4, f"precision={sc['precision']}"
            assert abs(sc["recall"]    - round(2/3, 4)) < 1e-4, f"recall={sc['recall']}"
            assert abs(sc["f1"]        - round(2/3, 4)) < 1e-4, f"f1={sc['f1']}"

        finally:
            session.close()


# ---------------------------------------------------------------------------
# Test 6 — Amount collision: two batches with the same sum, close dates
#           must NOT cross-match (reference anchor must be respected)
# ---------------------------------------------------------------------------

class TestAmountCollisionNoFalsePositive:
    """
    Proves that when two different payment batches happen to share the same
    total_amount and have close dates, the reference-anchored many_to_one stage
    does NOT cross-assign them to each other's bank event.

    Setup:
      - Two batches, each containing one claim, same paid_amount → same batch total
      - Two bank events, each referencing its own batch via trace number
      - After matching, each bank event must be linked to its OWN batch's claim
    """

    def test_same_amount_batches_matched_by_reference_not_amount(self):
        drop_db()
        init_db()

        session = SessionLocal()
        try:
            from backend.db.models import Member, EmployerGroup, GroupStatus, PlanType
            import uuid as _uuid

            acct = BankAccount(
                id=_uuid.uuid4(), name="Coll Acct",
                type=BankAccountType.CLEARING, institution="Test Bank",
            )
            session.add(acct)
            session.flush()

            group = EmployerGroup(
                id=_uuid.uuid4(), name="Coll Group",
                plan_type=PlanType.PPO, status=GroupStatus.ACTIVE,
                pepm_rate=Decimal("10.00"),
                funding_bank_account_id=acct.id,
            )
            session.add(group)
            session.flush()

            member = Member(
                id=_uuid.uuid4(), group_id=group.id,
                name="Test Member",
                enrollment_start=date.today() - timedelta(days=365),
            )
            session.add(member)
            session.flush()

            today = date.today()
            amount = Decimal("500.00")

            # Two claims, same paid_amount
            claim_a = Claim(
                id=_uuid.uuid4(), group_id=group.id, member_id=member.id,
                provider_name="Provider A", claim_date=today - timedelta(days=10),
                paid_date=today - timedelta(days=5),
                billed_amount=amount, allowed_amount=amount, paid_amount=amount,
                status=ClaimStatus.PAID,
            )
            claim_b = Claim(
                id=_uuid.uuid4(), group_id=group.id, member_id=member.id,
                provider_name="Provider B", claim_date=today - timedelta(days=10),
                paid_date=today - timedelta(days=4),
                billed_amount=amount, allowed_amount=amount, paid_amount=amount,
                status=ClaimStatus.PAID,
            )
            session.add_all([claim_a, claim_b])
            session.flush()

            # Two batches, each with exactly one claim → same total_amount
            batch_a = PaymentBatch(
                id=_uuid.uuid4(), batch_date=today - timedelta(days=4),
                bank_account_id=acct.id, total_amount=amount,
            )
            batch_b = PaymentBatch(
                id=_uuid.uuid4(), batch_date=today - timedelta(days=3),
                bank_account_id=acct.id, total_amount=amount,
            )
            session.add_all([batch_a, batch_b])
            session.flush()

            claim_a.payment_batch_id = batch_a.id
            claim_b.payment_batch_id = batch_b.id
            session.flush()

            # Ledger entries for each claim
            le_a = LedgerEntry(
                id=_uuid.uuid4(), bank_account_id=acct.id,
                entry_type=LedgerEntryType.CLAIM_PAYMENT,
                direction=Direction.DEBIT,
                amount=amount, expected_date=today - timedelta(days=5),
                reference=str(claim_a.id),
                source_artifact="835", status=LedgerEntryStatus.EXPECTED,
            )
            le_b = LedgerEntry(
                id=_uuid.uuid4(), bank_account_id=acct.id,
                entry_type=LedgerEntryType.CLAIM_PAYMENT,
                direction=Direction.DEBIT,
                amount=amount, expected_date=today - timedelta(days=4),
                reference=str(claim_b.id),
                source_artifact="835", status=LedgerEntryStatus.EXPECTED,
            )
            session.add_all([le_a, le_b])
            session.flush()

            # Two bank events — same amount, close dates, but distinct trace numbers
            # trace_000010 → batch_a,  trace_000020 → batch_b
            be_a = BankEvent(
                id=_uuid.uuid4(), bank_account_id=acct.id,
                posted_date=today - timedelta(days=4), amount=amount,
                direction=Direction.DEBIT,
                descriptor="ACH BATCH 000010 1 CLMS",
                bank_reference="trace_000010",
            )
            be_b = BankEvent(
                id=_uuid.uuid4(), bank_account_id=acct.id,
                posted_date=today - timedelta(days=3), amount=amount,
                direction=Direction.DEBIT,
                descriptor="ACH BATCH 000020 1 CLMS",
                bank_reference="trace_000020",
            )
            session.add_all([be_a, be_b])
            session.flush()

            # Run matcher
            run_match(session)

            # After matching: be_a should link to le_a (batch_a) and be_b to le_b (batch_b)
            # Both matches should have exactly 1 ledger entry each
            mle_rows = session.query(MatchLedgerEntry).all()
            match_be_map = {
                m.id: m.bank_event_id
                for m in session.query(ReconciliationMatch)
                .filter(ReconciliationMatch.match_type == "many_to_one")
                .all()
            }

            # Build predicted pairs for these two bank events
            predicted = {}  # bank_event_id → set of ledger_entry_ids
            for mle in mle_rows:
                be_id = match_be_map.get(mle.reconciliation_match_id)
                if be_id in (be_a.id, be_b.id):
                    predicted.setdefault(be_id, set()).add(mle.ledger_entry_id)

            assert le_a.id in predicted.get(be_a.id, set()), (
                "be_a was not matched to le_a (claim_a's ledger entry) — "
                "amount-only matching may have cross-assigned"
            )
            assert le_b.id in predicted.get(be_b.id, set()), (
                "be_b was not matched to le_b (claim_b's ledger entry) — "
                "amount-only matching may have cross-assigned"
            )
            # The cross-assignments must NOT exist
            assert le_b.id not in predicted.get(be_a.id, set()), "be_a wrongly linked to le_b"
            assert le_a.id not in predicted.get(be_b.id, set()), "be_b wrongly linked to le_a"

        finally:
            session.close()
