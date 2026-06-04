"""
Pytest test suite for Tieout Step 4 — exception resolution workflow.

Design
------
One module-scoped fixture (step4_db) creates a fresh database with a set of
bank events and matches, each assigned to exactly one test class.  State-
modifying tests within a class run in definition order (pytest default).

Dedicated bank events per class
  be_accept       → TestAcceptException
  be_match        → TestMatchException
  be_split        → TestSplitException  (exact split)
  be_split_partial→ TestSplitException  (partial / over-allocated)
  be_writeoff     → TestWriteOffException
  be_flag         → TestFlagException
  be_reopen       → TestReopenException (starts as MATCHED)
  be_audit        → TestAuditTimeline
  (Stats and List use the full state left by the module fixture.)
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func

from backend.db.connection import SessionLocal, drop_db, init_db
from backend.db.models import (
    AuditLog,
    BankAccount, BankAccountType,
    BankEvent, Direction,
    LedgerEntry, LedgerEntryStatus, LedgerEntryType,
    MatchLedgerEntry,
    ReconciliationMatch, ReconciliationMatchStatus,
)
from backend.exceptions import service


# ===========================================================================
# Module-scoped fixture: fresh DB with controlled initial state
# ===========================================================================

@pytest.fixture(scope="module")
def step4_db():
    drop_db()
    init_db()

    session = SessionLocal()

    acct = BankAccount(
        id=uuid.uuid4(), name="Test Clearing",
        type=BankAccountType.CLEARING, institution="Test Bank",
    )
    session.add(acct)
    session.flush()

    today = date.today()

    # ── Bank events ──────────────────────────────────────────────────────
    def be(amount, days_ago=0, descriptor="TEST", ref=None):
        return BankEvent(
            id=uuid.uuid4(), bank_account_id=acct.id,
            posted_date=today - timedelta(days=days_ago),
            amount=Decimal(str(amount)), direction=Direction.DEBIT,
            descriptor=descriptor, bank_reference=ref,
        )

    be_accept        = be("100.00", 5,  "ACCEPT TEST",        "ref-accept")
    be_match         = be("250.00", 10, "MATCH TEST",         "ref-match")
    be_split         = be("100.00", 3,  "SPLIT EXACT",        "ref-split")
    be_split_partial = be("100.00", 4,  "SPLIT PARTIAL",      "ref-splitp")
    be_writeoff      = be("75.00",  20, "WRITEOFF TEST",      None)
    be_flag          = be("200.00", 7,  "FLAG TEST",          None)
    be_reopen        = be("500.00", 1,  "AUTO MATCHED",       "ref-reopen")
    be_audit         = be("150.00", 15, "AUDIT TIMELINE",     "ref-audit")

    session.add_all([
        be_accept, be_match, be_split, be_split_partial,
        be_writeoff, be_flag, be_reopen, be_audit,
    ])
    session.flush()

    # ── Ledger entries ───────────────────────────────────────────────────
    def le(amount, days_ago=0, ref=None, entry_type=LedgerEntryType.EMPLOYER_FUNDING):
        return LedgerEntry(
            id=uuid.uuid4(), bank_account_id=acct.id,
            entry_type=entry_type, direction=Direction.DEBIT,
            amount=Decimal(str(amount)),
            expected_date=today - timedelta(days=days_ago),
            reference=ref,
            source_artifact="820", status=LedgerEntryStatus.EXPECTED,
        )

    le_accept     = le("100.00", 5,  "ref-accept")
    le_match_a    = le("150.00", 10, "ref-match-a")
    le_match_b    = le("100.00", 10, "ref-match-b")
    le_match_alt  = le( "90.00",  9, "ref-match-alt")  # free entry for manual match
    le_split_a    = le( "60.00",  3, "ref-split-a")
    le_split_b    = le( "40.00",  3, "ref-split-b")
    le_writeoff   = le( "75.00", 20, "ref-writeoff")
    le_flag       = le("200.00",  7, "ref-flag")
    le_reopen     = le("500.00",  1, "ref-reopen")
    le_audit      = le("150.00", 15, "ref-audit")
    le_free       = le( "80.00",  6, "ref-free")       # unlinked; used as a swap target

    session.add_all([
        le_accept, le_match_a, le_match_b, le_match_alt,
        le_split_a, le_split_b, le_writeoff, le_flag,
        le_reopen, le_audit, le_free,
    ])
    session.flush()

    # ── ReconciliationMatch rows ─────────────────────────────────────────
    def match(be_obj, match_type, conf, status):
        return ReconciliationMatch(
            id=uuid.uuid4(), bank_event_id=be_obj.id,
            match_type=match_type, confidence=Decimal(str(conf)),
            status=status,
        )

    NR = ReconciliationMatchStatus.NEEDS_REVIEW
    MA = ReconciliationMatchStatus.MATCHED

    m_accept        = match(be_accept,        "fuzzy",     "0.7500", NR)
    m_match         = match(be_match,         "many_to_one","0.7500", NR)
    m_split         = match(be_split,         "unmatched", "0.0000", NR)
    m_split_partial = match(be_split_partial, "unmatched", "0.0000", NR)
    m_writeoff      = match(be_writeoff,      "unmatched", "0.0000", NR)
    m_flag          = match(be_flag,          "fuzzy",     "0.6800", NR)
    m_reopen        = match(be_reopen,        "exact",     "1.0000", MA)
    m_audit         = match(be_audit,         "fuzzy",     "0.7200", NR)

    session.add_all([
        m_accept, m_match, m_split, m_split_partial,
        m_writeoff, m_flag, m_reopen, m_audit,
    ])
    session.flush()

    # ── MatchLedgerEntry links ───────────────────────────────────────────
    def link(match_obj, le_obj):
        session.add(MatchLedgerEntry(
            id=uuid.uuid4(),
            reconciliation_match_id=match_obj.id,
            ledger_entry_id=le_obj.id,
        ))

    link(m_accept,  le_accept)
    link(m_match,   le_match_a)
    link(m_match,   le_match_b)
    link(m_writeoff, le_writeoff)
    link(m_flag,    le_flag)
    link(m_reopen,  le_reopen)
    link(m_audit,   le_audit)
    # m_split and m_split_partial are "unmatched" — no ledger entries

    # Capture all IDs as plain Python values while session is still open.
    # Must happen before commit (expire_on_commit) and before close.
    ctx = {
        "acct_id":           acct.id,
        # bank event IDs
        "be_accept":         be_accept.id,
        "be_match":          be_match.id,
        "be_split":          be_split.id,
        "be_split_partial":  be_split_partial.id,
        "be_writeoff":       be_writeoff.id,
        "be_flag":           be_flag.id,
        "be_reopen":         be_reopen.id,
        "be_audit":          be_audit.id,
        # ledger entry IDs
        "le_accept":         le_accept.id,
        "le_match_a":        le_match_a.id,
        "le_match_b":        le_match_b.id,
        "le_match_alt":      le_match_alt.id,
        "le_split_a":        le_split_a.id,
        "le_split_b":        le_split_b.id,
        "le_writeoff":       le_writeoff.id,
        "le_flag":           le_flag.id,
        "le_reopen":         le_reopen.id,
        "le_audit":          le_audit.id,
        "le_free":           le_free.id,
        # amounts (Decimal — safe to copy before commit)
        "amount_split":      be_split.amount,
        "amount_split_p":    be_split_partial.amount,
    }

    session.commit()
    session.close()  # release connection; tests all use their own fresh_session()

    yield ctx


# ===========================================================================
# Helper
# ===========================================================================

def fresh_session():
    return SessionLocal()


def _get_match(session, be_id):
    return (
        session.query(ReconciliationMatch)
        .filter(ReconciliationMatch.bank_event_id == be_id)
        .first()
    )


def _audit_count(session, be_id, action=None):
    q = session.query(func.count(AuditLog.id)).filter(
        AuditLog.entity_type == "reconciliation_match",
        AuditLog.payload["bank_event_id"].astext == str(be_id),
    )
    if action:
        q = q.filter(AuditLog.action == action)
    return q.scalar() or 0


# ===========================================================================
# TestAcceptException
# ===========================================================================

class TestAcceptException:
    def test_accept_moves_to_resolved(self, step4_db):
        """needs_review → resolved after accept."""
        session = fresh_session()
        try:
            result = service.accept_exception(
                session, step4_db["be_accept"], note="looks right"
            )
            session.commit()
            assert result["new_status"] == "resolved"
            assert result["action"] == "accept"

            match = _get_match(session, step4_db["be_accept"])
            assert match.status == ReconciliationMatchStatus.RESOLVED
            assert match.resolved_by == "operator"
            assert match.resolved_at is not None
        finally:
            session.close()

    def test_accept_writes_audit_with_correct_before_after(self, step4_db):
        """Audit row has before=needs_review, after=resolved, bank_event_id in payload."""
        session = fresh_session()
        try:
            # be_accept is now resolved (from previous test)
            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "reconciliation_match",
                    AuditLog.payload["bank_event_id"].astext == str(step4_db["be_accept"]),
                    AuditLog.action == "accept",
                )
                .first()
            )
            assert entry is not None
            assert entry.payload["before"]["status"] == "needs_review"
            assert entry.payload["after"]["status"] == "resolved"
            assert entry.payload["note"] == "looks right"
            assert entry.payload["bank_event_id"] == str(step4_db["be_accept"])
        finally:
            session.close()

    def test_accept_idempotent_no_duplicate_audit(self, step4_db):
        """Accepting an already-resolved match is a no-op: no second audit row."""
        session = fresh_session()
        try:
            audit_before = _audit_count(session, step4_db["be_accept"], action="accept")

            result = service.accept_exception(session, step4_db["be_accept"])
            session.commit()

            assert result.get("idempotent") is True
            audit_after = _audit_count(session, step4_db["be_accept"], action="accept")
            assert audit_after == audit_before  # no new row
        finally:
            session.close()


# ===========================================================================
# TestMatchException
# ===========================================================================

class TestMatchException:
    def test_match_creates_correct_le_rows(self, step4_db):
        """Manual match replaces existing links with the supplied ledger entries."""
        session = fresh_session()
        try:
            # Replace the engine's suggestion with a single alt entry
            result = service.match_exception(
                session,
                step4_db["be_match"],
                [step4_db["le_match_alt"]],
                note="manual reassignment",
            )
            session.commit()
            assert result["new_status"] == "resolved"

            mle_rows = (
                session.query(MatchLedgerEntry)
                .join(ReconciliationMatch, MatchLedgerEntry.reconciliation_match_id == ReconciliationMatch.id)
                .filter(ReconciliationMatch.bank_event_id == step4_db["be_match"])
                .all()
            )
            le_ids = {r.ledger_entry_id for r in mle_rows}
            assert le_ids == {step4_db["le_match_alt"]}
        finally:
            session.close()

    def test_match_sets_type_to_manual(self, step4_db):
        """After manual match, match_type = 'manual'."""
        session = fresh_session()
        try:
            m = _get_match(session, step4_db["be_match"])
            assert m.match_type == "manual"
        finally:
            session.close()

    def test_match_writes_audit(self, step4_db):
        """Audit row captures before/after ledger_entry_ids."""
        session = fresh_session()
        try:
            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "reconciliation_match",
                    AuditLog.payload["bank_event_id"].astext == str(step4_db["be_match"]),
                    AuditLog.action == "match",
                )
                .first()
            )
            assert entry is not None
            # Before had the engine's two suggestions; after has the alt entry
            assert len(entry.payload["before"]["ledger_entry_ids"]) == 2
            assert str(step4_db["le_match_alt"]) in entry.payload["after"]["ledger_entry_ids"]
        finally:
            session.close()

    def test_match_invalid_le_raises(self, step4_db):
        """Passing a non-existent ledger_entry_id raises ValueError."""
        session = fresh_session()
        try:
            with pytest.raises(ValueError, match="LedgerEntry .* not found"):
                service.match_exception(
                    session, step4_db["be_match"], [uuid.uuid4()]
                )
        finally:
            session.close()


# ===========================================================================
# TestSplitException
# ===========================================================================

class TestSplitException:
    def test_split_over_sum_rejected(self, step4_db):
        """Allocations summing to MORE than bank amount are rejected."""
        session = fresh_session()
        try:
            allocs = [
                {"ledger_entry_id": step4_db["le_split_a"], "allocated_amount": Decimal("60.00")},
                {"ledger_entry_id": step4_db["le_split_b"], "allocated_amount": Decimal("50.00")},
                # 60 + 50 = 110 > 100
            ]
            with pytest.raises(ValueError, match="exceeds bank event amount"):
                service.split_exception(session, step4_db["be_split"], allocs)
            # No state change
            m = _get_match(session, step4_db["be_split"])
            assert m.status == ReconciliationMatchStatus.NEEDS_REVIEW
        finally:
            session.close()

    def test_split_exact_sum_resolved(self, step4_db):
        """Allocations summing exactly to bank amount → resolved/split."""
        session = fresh_session()
        try:
            allocs = [
                {"ledger_entry_id": step4_db["le_split_a"], "allocated_amount": Decimal("60.00")},
                {"ledger_entry_id": step4_db["le_split_b"], "allocated_amount": Decimal("40.00")},
            ]
            result = service.split_exception(
                session, step4_db["be_split"], allocs, note="exact split"
            )
            session.commit()
            assert result["new_status"] == "resolved"
            assert Decimal(result["remainder"]) == 0

            m = _get_match(session, step4_db["be_split"])
            assert m.status == ReconciliationMatchStatus.RESOLVED
            assert m.match_type == "split"

            # MatchLedgerEntry rows have allocated_amount set
            mle_rows = (
                session.query(MatchLedgerEntry)
                .filter(MatchLedgerEntry.reconciliation_match_id == m.id)
                .all()
            )
            assert len(mle_rows) == 2
            amounts = {r.allocated_amount for r in mle_rows}
            assert Decimal("60.00") in amounts
            assert Decimal("40.00") in amounts
        finally:
            session.close()

    def test_split_partial_sum_partially_resolved(self, step4_db):
        """Allocations summing to LESS than bank amount → partially_resolved."""
        session = fresh_session()
        try:
            allocs = [
                {"ledger_entry_id": step4_db["le_split_a"], "allocated_amount": Decimal("60.00")},
                {"ledger_entry_id": step4_db["le_split_b"], "allocated_amount": Decimal("30.00")},
                # 60 + 30 = 90 < 100 → remainder 10
            ]
            result = service.split_exception(
                session, step4_db["be_split_partial"], allocs, note="partial demo"
            )
            session.commit()
            assert result["new_status"] == "partially_resolved"
            assert Decimal(result["remainder"]) == Decimal("10.00")
        finally:
            session.close()

    def test_split_partial_records_remainder_in_notes_and_audit(self, step4_db):
        """The remainder is recorded in match.notes and the audit payload."""
        session = fresh_session()
        try:
            m = _get_match(session, step4_db["be_split_partial"])
            assert m.status == ReconciliationMatchStatus.PARTIALLY_RESOLVED
            assert "10" in (m.notes or "")  # remainder mentioned in notes

            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "reconciliation_match",
                    AuditLog.payload["bank_event_id"].astext == str(step4_db["be_split_partial"]),
                    AuditLog.action == "split",
                )
                .first()
            )
            assert entry is not None
            assert entry.payload["after"]["remainder"] == "10.00"
        finally:
            session.close()

    def test_split_partial_stays_in_queue(self, step4_db):
        """A partially_resolved item still appears in list_exceptions."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session)
            ids_in_queue = {item["bank_event_id"] for item in result["items"]}
            assert str(step4_db["be_split_partial"]) in ids_in_queue
        finally:
            session.close()


# ===========================================================================
# TestWriteOffException
# ===========================================================================

class TestWriteOffException:
    def test_write_off_moves_to_written_off(self, step4_db):
        """Write-off transitions needs_review → written_off."""
        session = fresh_session()
        try:
            result = service.write_off_exception(
                session, step4_db["be_writeoff"],
                reason="bank fee — no ledger counterpart",
            )
            session.commit()
            assert result["new_status"] == "written_off"

            m = _get_match(session, step4_db["be_writeoff"])
            assert m.status == ReconciliationMatchStatus.WRITTEN_OFF
            assert "bank fee" in (m.notes or "")
        finally:
            session.close()

    def test_write_off_idempotent(self, step4_db):
        """Calling write-off twice is safe; no duplicate audit rows."""
        session = fresh_session()
        try:
            audit_before = _audit_count(session, step4_db["be_writeoff"], action="write_off")

            result = service.write_off_exception(
                session, step4_db["be_writeoff"], reason="duplicate call"
            )
            session.commit()

            assert result.get("idempotent") is True
            audit_after = _audit_count(session, step4_db["be_writeoff"], action="write_off")
            assert audit_after == audit_before
        finally:
            session.close()

    def test_write_off_writes_audit(self, step4_db):
        """Audit row has correct before/after."""
        session = fresh_session()
        try:
            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "reconciliation_match",
                    AuditLog.payload["bank_event_id"].astext == str(step4_db["be_writeoff"]),
                    AuditLog.action == "write_off",
                )
                .first()
            )
            assert entry is not None
            assert entry.payload["before"]["status"] == "needs_review"
            assert entry.payload["after"]["status"] == "written_off"
        finally:
            session.close()


# ===========================================================================
# TestFlagException
# ===========================================================================

class TestFlagException:
    def test_flag_moves_to_flagged(self, step4_db):
        """Flag transitions needs_review → flagged."""
        session = fresh_session()
        try:
            result = service.flag_exception(
                session, step4_db["be_flag"], note="needs director sign-off"
            )
            session.commit()
            assert result["new_status"] == "flagged"

            m = _get_match(session, step4_db["be_flag"])
            assert m.status == ReconciliationMatchStatus.FLAGGED
        finally:
            session.close()

    def test_flag_stays_in_queue(self, step4_db):
        """Flagged items appear in list_exceptions (default queue includes flagged)."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session)
            ids_in_queue = {item["bank_event_id"] for item in result["items"]}
            assert str(step4_db["be_flag"]) in ids_in_queue
        finally:
            session.close()

    def test_flag_writes_audit(self, step4_db):
        session = fresh_session()
        try:
            entry = (
                session.query(AuditLog)
                .filter(
                    AuditLog.entity_type == "reconciliation_match",
                    AuditLog.payload["bank_event_id"].astext == str(step4_db["be_flag"]),
                    AuditLog.action == "flag",
                )
                .first()
            )
            assert entry is not None
            assert entry.payload["note"] == "needs director sign-off"
        finally:
            session.close()


# ===========================================================================
# TestReopenException
# ===========================================================================

class TestReopenException:
    def test_reopen_matched_to_needs_review(self, step4_db):
        """matched → needs_review via reopen."""
        session = fresh_session()
        try:
            m_before = _get_match(session, step4_db["be_reopen"])
            assert m_before.status == ReconciliationMatchStatus.MATCHED

            result = service.reopen_exception(
                session, step4_db["be_reopen"],
                note="operator suspects bad auto-match",
            )
            session.commit()
            assert result["new_status"] == "needs_review"

            m_after = _get_match(session, step4_db["be_reopen"])
            assert m_after.status == ReconciliationMatchStatus.NEEDS_REVIEW
            assert m_after.resolved_at is None
        finally:
            session.close()

    def test_reopen_idempotent_already_needs_review(self, step4_db):
        """Reopening an already-needs_review item returns idempotent flag."""
        session = fresh_session()
        try:
            result = service.reopen_exception(session, step4_db["be_reopen"])
            session.commit()
            assert result.get("idempotent") is True
        finally:
            session.close()

    def test_reopen_non_matched_raises(self, step4_db):
        """Reopening a resolved item raises ValueError."""
        session = fresh_session()
        try:
            # be_accept is resolved (from TestAcceptException)
            with pytest.raises(ValueError, match="reopen requires status=matched"):
                service.reopen_exception(session, step4_db["be_accept"])
        finally:
            session.close()


# ===========================================================================
# TestAuditTimeline
# ===========================================================================

class TestAuditTimeline:
    def test_accept_reopen_match_timeline(self, step4_db):
        """
        Full lifecycle: accept → reopen → manual-match produces 3 audit entries
        in chronological order, all keyed to the same bank_event_id.
        """
        session = fresh_session()
        try:
            be_id = step4_db["be_audit"]

            # Step 1: accept
            service.accept_exception(session, be_id, note="initial accept")
            session.commit()

            # Step 2: reopen (must move to MATCHED first for reopen to be valid)
            m = _get_match(session, be_id)
            m.status = ReconciliationMatchStatus.MATCHED
            session.flush()
            session.commit()

            service.reopen_exception(session, be_id, note="actually wrong")
            session.commit()

            # Step 3: manual match
            service.match_exception(
                session, be_id, [step4_db["le_free"]], note="correct assignment"
            )
            session.commit()

            history = service.get_audit_history(session, be_id)

            # All entries anchored on same bank_event_id
            for entry in history:
                assert entry["payload"]["bank_event_id"] == str(be_id)

            # Must have at least the three actions we performed
            actions = [e["action"] for e in history]
            assert "accept" in actions
            assert "reopen" in actions
            assert "match" in actions

            # Chronological order
            timestamps = [e["created_at"] for e in history]
            assert timestamps == sorted(timestamps)
        finally:
            session.close()

    def test_audit_bank_event_id_in_every_payload(self, step4_db):
        """Every audit row for reconciliation_match actions carries bank_event_id."""
        session = fresh_session()
        try:
            rows = (
                session.query(AuditLog)
                .filter(AuditLog.entity_type == "reconciliation_match")
                .all()
            )
            assert rows, "No audit rows found — earlier action tests must run first"
            for row in rows:
                assert "bank_event_id" in (row.payload or {}), (
                    f"Audit row {row.id} (action={row.action}) missing bank_event_id in payload"
                )
        finally:
            session.close()


# ===========================================================================
# TestListExceptions  — uses leftover state from action tests
# ===========================================================================

class TestListExceptions:
    def test_list_returns_only_queue_statuses(self, step4_db):
        """Default list returns only needs_review, flagged, partially_resolved."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session)
            for item in result["items"]:
                assert item["status"] in ("needs_review", "flagged", "partially_resolved"), (
                    f"Item {item['bank_event_id']} has unexpected status {item['status']}"
                )
        finally:
            session.close()

    def test_list_filter_by_match_type(self, step4_db):
        """Filtering by match_type returns only matching rows."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session, match_type="fuzzy")
            for item in result["items"]:
                assert item["match_type"] == "fuzzy"
        finally:
            session.close()

    def test_list_filter_by_bank_account(self, step4_db):
        """Filtering by bank_account_id scopes results to that account."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session, bank_account_id=step4_db["acct_id"])
            assert result["total"] >= 1
            for item in result["items"]:
                assert item["bank_account_id"] == str(step4_db["acct_id"])
        finally:
            session.close()

    def test_list_sort_amount_desc(self, step4_db):
        """amount_desc sort returns largest first."""
        session = fresh_session()
        try:
            result = service.list_exceptions(session, sort="amount_desc")
            amounts = [Decimal(item["amount"]) for item in result["items"]]
            assert amounts == sorted(amounts, reverse=True)
        finally:
            session.close()

    def test_list_pagination(self, step4_db):
        """Pagination returns correct subset."""
        session = fresh_session()
        try:
            page1 = service.list_exceptions(session, page=1, page_size=2)
            page2 = service.list_exceptions(session, page=2, page_size=2)
            assert len(page1["items"]) <= 2
            # IDs must not overlap between pages
            ids1 = {i["bank_event_id"] for i in page1["items"]}
            ids2 = {i["bank_event_id"] for i in page2["items"]}
            assert ids1.isdisjoint(ids2)
        finally:
            session.close()


# ===========================================================================
# TestGetExceptionDetail  — uses leftover state
# ===========================================================================

class TestGetExceptionDetail:
    def test_detail_returns_bank_event_info(self, step4_db):
        """Detail includes bank event amount, descriptor, direction."""
        session = fresh_session()
        try:
            # Use be_reopen (now needs_review after reopen test)
            detail = service.get_exception_detail(session, step4_db["be_reopen"])
            be_data = detail["bank_event"]
            assert Decimal(be_data["amount"]) == Decimal("500.00")
            assert be_data["direction"] == "debit"
            assert "AUTO MATCHED" in be_data["descriptor"]
        finally:
            session.close()

    def test_detail_includes_why_uncertain(self, step4_db):
        """why_uncertain is a non-empty string."""
        session = fresh_session()
        try:
            detail = service.get_exception_detail(session, step4_db["be_reopen"])
            assert isinstance(detail["why_uncertain"], str)
            assert len(detail["why_uncertain"]) > 0
        finally:
            session.close()

    def test_detail_candidates_are_scored(self, step4_db):
        """Each candidate has a score between 0 and 1 and at least one reason."""
        session = fresh_session()
        try:
            detail = service.get_exception_detail(session, step4_db["be_reopen"])
            for cand in detail["candidates"]:
                assert 0.0 < cand["score"] <= 1.0
                assert cand["score_reasons"]
                assert "id" in cand["ledger_entry"]
        finally:
            session.close()

    def test_detail_not_found_raises(self, step4_db):
        """Requesting detail for a non-existent bank_event_id raises ValueError."""
        session = fresh_session()
        try:
            with pytest.raises(ValueError, match="No reconciliation match found"):
                service.get_exception_detail(session, uuid.uuid4())
        finally:
            session.close()


# ===========================================================================
# TestStats  — MUST be last: calls drop_db() which destroys step4_db fixture data
# ===========================================================================

class TestStats:
    """Uses its own fresh database so counts are fully deterministic."""

    def test_stats_counts_and_amounts(self):
        drop_db()
        init_db()

        session = fresh_session()
        try:
            acct = BankAccount(
                id=uuid.uuid4(), name="Stats Acct",
                type=BankAccountType.CLEARING, institution="Stats Bank",
            )
            session.add(acct)
            session.flush()

            today = date.today()

            def mk_be(amount):
                b = BankEvent(
                    id=uuid.uuid4(), bank_account_id=acct.id,
                    posted_date=today, amount=Decimal(str(amount)),
                    direction=Direction.DEBIT, descriptor="STATS",
                )
                session.add(b)
                return b

            def mk_match(be_obj, status, match_type="fuzzy", conf="0.70"):
                m = ReconciliationMatch(
                    id=uuid.uuid4(), bank_event_id=be_obj.id,
                    match_type=match_type, confidence=Decimal(conf),
                    status=status,
                )
                session.add(m)
                return m

            NR  = ReconciliationMatchStatus.NEEDS_REVIEW
            MA  = ReconciliationMatchStatus.MATCHED
            RES = ReconciliationMatchStatus.RESOLVED
            WO  = ReconciliationMatchStatus.WRITTEN_OFF
            FL  = ReconciliationMatchStatus.FLAGGED
            PR  = ReconciliationMatchStatus.PARTIALLY_RESOLVED

            # 3 needs_review ($50 + $75 + $100 = $225 unresolved)
            mk_match(mk_be("50.00"),  NR)
            mk_match(mk_be("75.00"),  NR)
            mk_match(mk_be("100.00"), NR)
            # 1 matched (not unresolved)
            mk_match(mk_be("500.00"), MA, match_type="exact", conf="1.00")
            # 1 resolved
            mk_match(mk_be("200.00"), RES, match_type="manual")
            # 1 written_off
            mk_match(mk_be("30.00"),  WO)
            # 1 flagged ($150 unresolved)
            mk_match(mk_be("150.00"), FL)
            # 1 partially_resolved ($80 unresolved)
            mk_match(mk_be("80.00"),  PR, match_type="split")

            session.commit()

            stats = service.get_stats(session)

            assert stats["by_status"]["needs_review"]       == 3
            assert stats["by_status"]["matched"]            == 1
            assert stats["by_status"]["resolved"]           == 1
            assert stats["by_status"]["written_off"]        == 1
            assert stats["by_status"]["flagged"]            == 1
            assert stats["by_status"]["partially_resolved"] == 1
            assert stats["total_exceptions"]                == 8

            # Unresolved = needs_review ($225) + flagged ($150) + partially_resolved ($80)
            unresolved = Decimal(stats["total_unresolved_amount"])
            assert unresolved == Decimal("455.00"), f"Expected 455.00, got {unresolved}"

            # Oldest unresolved: all posted today, so 0 days
            assert stats["oldest_unresolved_days"] == 0
        finally:
            session.close()
