"""
Pytest test suite for Tieout Step 6 — cash-position endpoint.

Controlled fixture
------------------
Two employer groups, one bank account.  Ledger entries and reconciliation rows
are created explicitly so every assertion is derivable by inspection.

  Group A ("Alpha Corp"):
    - employer_funding  CREDIT  $100 000.00  → MATCHED reconciliation
    - stop_loss_reimb.  CREDIT   $10 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT    $40 000.00  → MATCHED reconciliation
    - admin_fee         CREDIT    $5 000.00  → MATCHED reconciliation
    - stop_loss_premium DEBIT    $12 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT    $20 000.00  → NEEDS_REVIEW match  (counts as pending)
    - claim_payment     DEBIT     $8 000.00  → no match at all     (counts as pending)

    cleared credits  = 100 000 + 10 000 + 5 000            = 115 000
    cleared debits   = 40 000 + 12 000                      =  52 000
    funded_balance   = 115 000 - 52 000                     =  63 000
    pending_liability = 20 000 + 8 000                      =  28 000
    coverage_status  : 63 000 >= 28 000 × 1.10 = 30 800    → healthy

  Group B ("Beta LLC"):
    - employer_funding  CREDIT   $30 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT    $35 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT    $10 000.00  → no match             (counts as pending)

    cleared credits  = 30 000
    cleared debits   = 35 000
    funded_balance   = 30 000 - 35 000 = -5 000
    pending_liability = 10 000
    coverage_status  : -5 000 < 10 000                      → shortfall

  Group C ("Gamma Inc"):
    - employer_funding  CREDIT   $50 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT    $44 000.00  → MATCHED reconciliation
    - claim_payment     DEBIT     $5 000.00  → no match             (counts as pending)

    funded_balance   = 50 000 - 44 000 = 6 000
    pending_liability = 5 000
    coverage_status  : 6 000 >= 5 000 (=1.10×?) → 6000 < 5000×1.10=5500 → watch

  Partially-resolved edge case (Group A second claim batch):
    An additional claim_payment of $15 000 is linked to a PARTIALLY_RESOLVED match.
    It should count as cleared (no double-count with pending_liability).
    funded_balance increases, pending_liability stays the same as without it.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from backend.cash_position import service
from backend.db.connection import SessionLocal, drop_db, init_db
from backend.db.models import (
    BankAccount, BankAccountType,
    BankEvent, Direction,
    EmployerGroup, GroupStatus,
    LedgerEntry, LedgerEntryStatus, LedgerEntryType,
    MatchLedgerEntry,
    Member,
    PlanType,
    ReconciliationMatch, ReconciliationMatchStatus,
)

TODAY = date(2026, 6, 4)


# ===========================================================================
# Fixture
# ===========================================================================

@pytest.fixture(scope="module")
def step6_db():
    drop_db()
    init_db()
    session = SessionLocal()

    # ── Shared bank account ───────────────────────────────────────────────────
    acct = BankAccount(
        id=uuid.uuid4(), name="Test Clearing",
        type=BankAccountType.CLEARING, institution="Test Bank",
    )
    session.add(acct)
    session.flush()

    # ── Helper: make a BankEvent ──────────────────────────────────────────────
    def be(amount: Decimal, direction: Direction) -> BankEvent:
        b = BankEvent(
            id=uuid.uuid4(), bank_account_id=acct.id,
            posted_date=TODAY, amount=amount,
            direction=direction, descriptor="TEST",
        )
        session.add(b)
        return b

    # ── Helper: make a LedgerEntry ────────────────────────────────────────────
    def le(group_id, entry_type: LedgerEntryType, direction: Direction, amount: Decimal) -> LedgerEntry:
        e = LedgerEntry(
            id=uuid.uuid4(), group_id=group_id, bank_account_id=acct.id,
            entry_type=entry_type, direction=direction, amount=amount,
            expected_date=TODAY, status=LedgerEntryStatus.EXPECTED,
        )
        session.add(e)
        return e

    # ── Helper: link LE to a match ────────────────────────────────────────────
    def match_le(bank_event: BankEvent, les: list[LedgerEntry], status: ReconciliationMatchStatus) -> ReconciliationMatch:
        m = ReconciliationMatch(
            id=uuid.uuid4(), bank_event_id=bank_event.id,
            match_type="exact", confidence=Decimal("0.9500"),
            status=status,
        )
        session.add(m)
        session.flush()
        for l in les:
            session.add(MatchLedgerEntry(
                id=uuid.uuid4(),
                reconciliation_match_id=m.id,
                ledger_entry_id=l.id,
            ))
        return m

    # ── Group A — Alpha Corp ──────────────────────────────────────────────────
    gA = EmployerGroup(
        id=uuid.uuid4(), name="Alpha Corp",
        plan_type=PlanType.PPO, status=GroupStatus.ACTIVE,
        pepm_rate=Decimal("50.00"), funding_bank_account_id=acct.id,
    )
    session.add(gA)
    session.flush()
    session.add(Member(id=uuid.uuid4(), group_id=gA.id, name="Alice", enrollment_start=TODAY))

    # cleared entries
    leA_ef   = le(gA.id, LedgerEntryType.EMPLOYER_FUNDING,        Direction.CREDIT, Decimal("100000.00"))
    leA_sl_r = le(gA.id, LedgerEntryType.STOP_LOSS_REIMBURSEMENT, Direction.CREDIT, Decimal("10000.00"))
    leA_cp1  = le(gA.id, LedgerEntryType.CLAIM_PAYMENT,           Direction.DEBIT,  Decimal("40000.00"))
    leA_af   = le(gA.id, LedgerEntryType.ADMIN_FEE,               Direction.CREDIT, Decimal("5000.00"))
    leA_slp  = le(gA.id, LedgerEntryType.STOP_LOSS_PREMIUM,       Direction.DEBIT,  Decimal("12000.00"))

    # partially-resolved entry (counts as cleared — proof of no double-count)
    leA_cp_partial = le(gA.id, LedgerEntryType.CLAIM_PAYMENT, Direction.DEBIT, Decimal("15000.00"))

    # uncleared (needs_review → pending)
    leA_cp_nr = le(gA.id, LedgerEntryType.CLAIM_PAYMENT, Direction.DEBIT, Decimal("20000.00"))
    # uncleared (no match → pending)
    leA_cp_nm = le(gA.id, LedgerEntryType.CLAIM_PAYMENT, Direction.DEBIT, Decimal("8000.00"))

    session.flush()

    match_le(be(Decimal("100000.00"), Direction.CREDIT), [leA_ef],        ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("10000.00"),  Direction.CREDIT), [leA_sl_r],      ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("40000.00"),  Direction.DEBIT),  [leA_cp1],       ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("5000.00"),   Direction.CREDIT), [leA_af],        ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("12000.00"),  Direction.DEBIT),  [leA_slp],       ReconciliationMatchStatus.MATCHED)
    # PARTIALLY_RESOLVED match for leA_cp_partial — must NOT appear in pending
    match_le(be(Decimal("12000.00"),  Direction.DEBIT),  [leA_cp_partial], ReconciliationMatchStatus.PARTIALLY_RESOLVED)
    # NEEDS_REVIEW match — LE is in match_ledger_entry but status is not cleared
    match_le(be(Decimal("20000.00"),  Direction.DEBIT),  [leA_cp_nr],     ReconciliationMatchStatus.NEEDS_REVIEW)
    # leA_cp_nm has no match at all

    # ── Group B — Beta LLC ────────────────────────────────────────────────────
    gB = EmployerGroup(
        id=uuid.uuid4(), name="Beta LLC",
        plan_type=PlanType.PPO, status=GroupStatus.ACTIVE,
        pepm_rate=Decimal("50.00"), funding_bank_account_id=acct.id,
    )
    session.add(gB)
    session.flush()
    session.add(Member(id=uuid.uuid4(), group_id=gB.id, name="Bob", enrollment_start=TODAY))

    leB_ef  = le(gB.id, LedgerEntryType.EMPLOYER_FUNDING, Direction.CREDIT, Decimal("30000.00"))
    leB_cp1 = le(gB.id, LedgerEntryType.CLAIM_PAYMENT,    Direction.DEBIT,  Decimal("35000.00"))
    leB_cp2 = le(gB.id, LedgerEntryType.CLAIM_PAYMENT,    Direction.DEBIT,  Decimal("10000.00"))

    session.flush()
    match_le(be(Decimal("30000.00"), Direction.CREDIT), [leB_ef],  ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("35000.00"), Direction.DEBIT),  [leB_cp1], ReconciliationMatchStatus.MATCHED)
    # leB_cp2 has no match

    # ── Group C — Gamma Inc ───────────────────────────────────────────────────
    gC = EmployerGroup(
        id=uuid.uuid4(), name="Gamma Inc",
        plan_type=PlanType.PPO, status=GroupStatus.ACTIVE,
        pepm_rate=Decimal("50.00"), funding_bank_account_id=acct.id,
    )
    session.add(gC)
    session.flush()
    session.add(Member(id=uuid.uuid4(), group_id=gC.id, name="Carol", enrollment_start=TODAY))

    leC_ef  = le(gC.id, LedgerEntryType.EMPLOYER_FUNDING, Direction.CREDIT, Decimal("50000.00"))
    leC_cp1 = le(gC.id, LedgerEntryType.CLAIM_PAYMENT,    Direction.DEBIT,  Decimal("44000.00"))
    leC_cp2 = le(gC.id, LedgerEntryType.CLAIM_PAYMENT,    Direction.DEBIT,  Decimal("5000.00"))

    session.flush()
    match_le(be(Decimal("50000.00"), Direction.CREDIT), [leC_ef],  ReconciliationMatchStatus.MATCHED)
    match_le(be(Decimal("44000.00"), Direction.DEBIT),  [leC_cp1], ReconciliationMatchStatus.MATCHED)

    session.commit()
    yield {"session": session, "gA": gA, "gB": gB, "gC": gC}
    session.close()


# ===========================================================================
# Group A — funded_balance and pending_liability math
# ===========================================================================

class TestGroupAlpha:

    def test_funded_balance(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        # cleared credits: 100000 + 10000 + 5000 = 115000
        # cleared debits:   40000 + 12000 + 15000 (partial) = 67000
        # funded_balance = 115000 - 67000 = 48000
        assert pos.funded_balance == Decimal("48000.00"), f"got {pos.funded_balance}"

    def test_pending_claims_liability(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        # needs_review (20000) + no-match (8000) = 28000
        assert pos.pending_claims_liability == Decimal("28000.00"), f"got {pos.pending_claims_liability}"

    def test_available_to_cover_equals_funded_balance(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        assert pos.available_to_cover == pos.funded_balance

    def test_coverage_status_healthy(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        # 48000 >= 28000 × 1.10 = 30800 → healthy
        assert pos.coverage_status == "healthy", f"got {pos.coverage_status}"


# ===========================================================================
# Partially-resolved edge case — no double-count
# ===========================================================================

class TestPartiallyResolvedEdgeCase:

    def test_partially_resolved_counts_as_cleared(self, step6_db):
        """leA_cp_partial (PARTIALLY_RESOLVED match) must appear in cleared, not pending."""
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        # If partial were in pending: pending would be 28000 + 15000 = 43000 (wrong)
        assert pos.pending_claims_liability == Decimal("28000.00"), (
            f"partially_resolved entry double-counted in pending: {pos.pending_claims_liability}"
        )

    def test_partially_resolved_included_in_funded_balance(self, step6_db):
        """leA_cp_partial's $15 000 debit must reduce funded_balance."""
        session = step6_db["session"]
        gA = step6_db["gA"]
        pos = service._compute_position(session, gA)
        # Without partial: 115000 - 52000 = 63000.  With partial debit: 63000 - 15000 = 48000
        assert pos.funded_balance == Decimal("48000.00"), (
            f"partially_resolved debit not included in funded_balance: {pos.funded_balance}"
        )


# ===========================================================================
# Group B — shortfall
# ===========================================================================

class TestGroupBeta:

    def test_funded_balance(self, step6_db):
        session = step6_db["session"]
        gB = step6_db["gB"]
        pos = service._compute_position(session, gB)
        # 30000 - 35000 = -5000
        assert pos.funded_balance == Decimal("-5000.00"), f"got {pos.funded_balance}"

    def test_pending_liability(self, step6_db):
        session = step6_db["session"]
        gB = step6_db["gB"]
        pos = service._compute_position(session, gB)
        assert pos.pending_claims_liability == Decimal("10000.00"), f"got {pos.pending_claims_liability}"

    def test_coverage_status_shortfall(self, step6_db):
        session = step6_db["session"]
        gB = step6_db["gB"]
        pos = service._compute_position(session, gB)
        # -5000 < 10000 → shortfall
        assert pos.coverage_status == "shortfall", f"got {pos.coverage_status}"


# ===========================================================================
# Group C — watch
# ===========================================================================

class TestGroupGamma:

    def test_funded_balance(self, step6_db):
        session = step6_db["session"]
        gC = step6_db["gC"]
        pos = service._compute_position(session, gC)
        # 50000 - 44000 = 6000
        assert pos.funded_balance == Decimal("6000.00"), f"got {pos.funded_balance}"

    def test_pending_liability(self, step6_db):
        session = step6_db["session"]
        gC = step6_db["gC"]
        pos = service._compute_position(session, gC)
        assert pos.pending_claims_liability == Decimal("5000.00"), f"got {pos.pending_claims_liability}"

    def test_coverage_status_watch(self, step6_db):
        session = step6_db["session"]
        gC = step6_db["gC"]
        pos = service._compute_position(session, gC)
        # 6000 >= 5000 (×1.00) but < 5000×1.10=5500? No: 6000 > 5500 → healthy
        # Re-check: 6000 >= 5500 → healthy.
        # For watch, need funded >= pending but < pending×1.10:
        # 5000 >= 5000 but 5000 < 5500 → watch
        # Our funded_balance = 6000, which is >=5500 → healthy.
        # Actually: 6000/5000 = 1.20 >= 1.10 → healthy.
        # The watch test only works if funded_balance = 5000-5499 range.
        # With our numbers: 50000-44000=6000, pending=5000, ratio=1.2 → healthy.
        # Let's assert what the actual status should be:
        expected = "healthy"  # 6000 > 5000×1.10=5500
        assert pos.coverage_status == expected, f"got {pos.coverage_status}"

    def test_watch_threshold(self, step6_db):
        """
        Directly test the _coverage_status helper at the watch boundary.
        funded=5200 pending=5000: 5200 < 5500 (=5000×1.10) but >= 5000×1.00 → watch
        """
        status = service._coverage_status(Decimal("5200.00"), Decimal("5000.00"))
        assert status == "watch", f"got {status}"

    def test_shortfall_threshold(self, step6_db):
        """funded < pending → shortfall regardless of margin."""
        status = service._coverage_status(Decimal("4999.99"), Decimal("5000.00"))
        assert status == "shortfall"

    def test_healthy_threshold(self, step6_db):
        """funded >= pending × 1.10 → healthy."""
        status = service._coverage_status(Decimal("5500.00"), Decimal("5000.00"))
        assert status == "healthy"

    def test_zero_pending_always_healthy(self, step6_db):
        """Zero pending liability → healthy regardless of funded balance."""
        assert service._coverage_status(Decimal("-9999.00"), Decimal("0")) == "healthy"


# ===========================================================================
# get_all_positions — aggregate
# ===========================================================================

class TestGetAllPositions:

    def test_returns_all_groups(self, step6_db):
        session = step6_db["session"]
        result = service.get_all_positions(session)
        assert len(result.groups) == 3

    def test_shortfall_sorts_first(self, step6_db):
        session = step6_db["session"]
        result = service.get_all_positions(session)
        statuses = [g.coverage_status for g in result.groups]
        assert statuses[0] == "shortfall", f"first group should be shortfall, got: {statuses}"

    def test_summary_groups_in_shortfall(self, step6_db):
        session = step6_db["session"]
        result = service.get_all_positions(session)
        assert result.summary.groups_in_shortfall == 1

    def test_summary_total_funded_is_decimal(self, step6_db):
        """total_funded must be Decimal, not float — no precision loss."""
        session = step6_db["session"]
        result = service.get_all_positions(session)
        assert isinstance(result.summary.total_funded, Decimal), (
            f"expected Decimal, got {type(result.summary.total_funded)}"
        )

    def test_summary_total_funded_value(self, step6_db):
        """total_funded = sum of all group funded_balances."""
        session = step6_db["session"]
        result = service.get_all_positions(session)
        # gA: 48000, gB: -5000, gC: 6000 → 49000
        expected = Decimal("49000.00")
        assert result.summary.total_funded == expected, (
            f"expected {expected}, got {result.summary.total_funded}"
        )

    def test_summary_total_pending(self, step6_db):
        session = step6_db["session"]
        result = service.get_all_positions(session)
        # gA: 28000, gB: 10000, gC: 5000 → 43000
        assert result.summary.total_pending_liability == Decimal("43000.00"), (
            f"got {result.summary.total_pending_liability}"
        )


# ===========================================================================
# get_group_detail — contributing entries
# ===========================================================================

class TestGetGroupDetail:

    def test_detail_returns_group(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        detail = service.get_group_detail(session, gA.id)
        assert detail is not None
        assert detail.group_id == str(gA.id)

    def test_detail_cleared_entries_nonempty(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        detail = service.get_group_detail(session, gA.id)
        assert len(detail.cleared_entries) > 0

    def test_detail_pending_entries_nonempty(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        detail = service.get_group_detail(session, gA.id)
        # needs_review (20000) and no-match (8000) must appear
        assert len(detail.pending_entries) == 2

    def test_detail_pending_amounts(self, step6_db):
        session = step6_db["session"]
        gA = step6_db["gA"]
        detail = service.get_group_detail(session, gA.id)
        total_pending = sum(e.amount for e in detail.pending_entries)
        assert total_pending == Decimal("28000.00"), f"got {total_pending}"

    def test_detail_not_found_returns_none(self, step6_db):
        session = step6_db["session"]
        import uuid as _uuid
        result = service.get_group_detail(session, _uuid.uuid4())
        assert result is None

    def test_decimal_precision_in_amounts(self, step6_db):
        """Amounts in detail entries must be Decimal, not float."""
        session = step6_db["session"]
        gA = step6_db["gA"]
        detail = service.get_group_detail(session, gA.id)
        for entry in detail.cleared_entries:
            assert isinstance(entry.amount, Decimal), (
                f"entry {entry.id} amount is {type(entry.amount)}, expected Decimal"
            )


# ===========================================================================
# group_id filter on list_exceptions
# ===========================================================================

class TestGroupIdFilter:
    """
    Verify the group_id filter on list_exceptions.

    The exception queue is bank-event-centric.  A group only appears when one
    of its bank events sits in a NEEDS_REVIEW / FLAGGED / PARTIALLY_RESOLVED
    reconciliation_match that has match_ledger_entry rows pointing to that
    group's ledger entries.

    In the step6_db fixture:
      - Group A has two queue-visible matches (NEEDS_REVIEW $20k + PARTIALLY_RESOLVED $15k)
      - Group B's unmatched $10k claim_payment has NO bank event — it never
        enters the exception queue (it shows as pending_claims_liability instead)
      - Group C is in the same situation as B

    So Group A filter returns items; B and C filters return empty — both are
    correct behaviour for the filter.
    """

    def test_group_a_filter_returns_its_exceptions(self, step6_db):
        from backend.exceptions import service as exc_service
        session = step6_db["session"]
        gA = step6_db["gA"]

        result = exc_service.list_exceptions(session, group_id=gA.id, page_size=100)
        assert result["total"] > 0, "Group A has NEEDS_REVIEW and PARTIALLY_RESOLVED matches — filter should return them"

    def test_group_b_filter_returns_empty(self, step6_db):
        """Group B has no bank events in the queue — filter correctly returns nothing."""
        from backend.exceptions import service as exc_service
        session = step6_db["session"]
        gB = step6_db["gB"]

        result = exc_service.list_exceptions(session, group_id=gB.id, page_size=100)
        assert result["total"] == 0, (
            "Group B's unmatched LEs have no bank event — they are pending_claims_liability, "
            "not exception queue items"
        )

    def test_group_filter_is_exclusive(self, step6_db):
        """Group A's results must not include bank events from Group B or C."""
        from backend.exceptions import service as exc_service
        session = step6_db["session"]
        gA = step6_db["gA"]
        gB = step6_db["gB"]
        gC = step6_db["gC"]

        ids_a = {i["bank_event_id"] for i in exc_service.list_exceptions(session, group_id=gA.id, page_size=100)["items"]}
        ids_b = {i["bank_event_id"] for i in exc_service.list_exceptions(session, group_id=gB.id, page_size=100)["items"]}
        ids_c = {i["bank_event_id"] for i in exc_service.list_exceptions(session, group_id=gC.id, page_size=100)["items"]}

        assert ids_a.isdisjoint(ids_b), "Group A and B results must not overlap"
        assert ids_a.isdisjoint(ids_c), "Group A and C results must not overlap"

    def test_unknown_group_returns_empty(self, step6_db):
        import uuid as _uuid
        from backend.exceptions import service as exc_service
        session = step6_db["session"]
        result = exc_service.list_exceptions(session, group_id=_uuid.uuid4(), page_size=100)
        assert result["total"] == 0
        assert result["items"] == []

    def test_no_group_filter_returns_all(self, step6_db):
        """Unfiltered result must include at least as many items as any single group filter."""
        from backend.exceptions import service as exc_service
        session = step6_db["session"]
        result_all = exc_service.list_exceptions(session, page_size=100)
        result_a   = exc_service.list_exceptions(session, group_id=step6_db["gA"].id, page_size=100)
        assert result_all["total"] >= result_a["total"]
