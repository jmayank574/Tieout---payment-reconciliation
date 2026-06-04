"""
resolve_demo.py - Exercises the Step 4 exception resolution workflow.

Assumes the database has already been seeded, ingested, and matched
(make seed && make match).  Walks one bank event through the full
accept -> reopen -> manual-match lifecycle, then prints its complete
audit trail to show the multi-step timeline.

Run:
    python -m backend.scripts.resolve_demo        (Windows, from repo root)
    PYTHONPATH=. python backend/scripts/resolve_demo.py
"""

from __future__ import annotations

import sys

from backend.db.connection import SessionLocal
from backend.db.models import (
    BankEvent,
    LedgerEntry,
    MatchLedgerEntry,
    ReconciliationMatch, ReconciliationMatchStatus,
)
from backend.exceptions import service


def _print_stats(label: str, stats: dict) -> None:
    print(f"\n{'='*56}")
    print(f"  {label}")
    print(f"{'='*56}")
    by_status = stats["by_status"]
    for status, count in sorted(by_status.items()):
        if count:
            print(f"  {status:<26} {count:>5}")
    print(f"  {'-'*32}")
    print(f"  {'total_exceptions':<26} {stats['total_exceptions']:>5}")
    print(f"  {'total_unresolved_amount':<26} ${stats['total_unresolved_amount']:>12}")
    if stats["oldest_unresolved_days"] is not None:
        print(f"  {'oldest_unresolved_days':<26} {stats['oldest_unresolved_days']:>5}")
    print(f"{'='*56}")


def _pick_needs_review(session) -> ReconciliationMatch | None:
    """Find any needs_review fuzzy match (best candidate for lifecycle demo)."""
    return (
        session.query(ReconciliationMatch)
        .filter(
            ReconciliationMatch.status == ReconciliationMatchStatus.NEEDS_REVIEW,
            ReconciliationMatch.match_type == "fuzzy",
        )
        .first()
    ) or (
        session.query(ReconciliationMatch)
        .filter(ReconciliationMatch.status == ReconciliationMatchStatus.NEEDS_REVIEW)
        .first()
    )


def _any_free_ledger_entry(session, bank_event_id):
    """Return a ledger entry on the same account/direction not already linked."""
    match = (
        session.query(ReconciliationMatch)
        .filter(ReconciliationMatch.bank_event_id == bank_event_id)
        .first()
    )
    linked_ids = {
        r.ledger_entry_id
        for r in session.query(MatchLedgerEntry)
        .filter(MatchLedgerEntry.reconciliation_match_id == match.id)
        .all()
    }
    be = session.query(BankEvent).filter(BankEvent.id == bank_event_id).first()
    return (
        session.query(LedgerEntry)
        .filter(
            LedgerEntry.bank_account_id == be.bank_account_id,
            LedgerEntry.direction == be.direction,
            ~LedgerEntry.id.in_(linked_ids),
        )
        .first()
    )


def main() -> None:
    session = SessionLocal()

    print("\n" + "=" * 56)
    print("  TIEOUT - RESOLVE DEMO  (Step 4 lifecycle)")
    print("=" * 56)

    stats_before = service.get_stats(session)
    _print_stats("BEFORE: queue state", stats_before)

    if not stats_before["by_status"].get("needs_review", 0):
        print("\nNo needs_review items.  Run: make seed && make match first.")
        session.close()
        sys.exit(1)

    # Pick one bank event for the full lifecycle
    m = _pick_needs_review(session)
    if not m:
        print("\nCould not find a suitable needs_review item.")
        session.close()
        sys.exit(1)

    be_id = m.bank_event_id
    be = session.query(BankEvent).filter(BankEvent.id == be_id).first()
    short_id = str(be_id)[:8]

    print(f"\n  Lifecycle event: bank_event {short_id}...")
    print(f"  amount={be.amount}  descriptor={be.descriptor!r}")
    print(f"  engine suggestion: match_type={m.match_type}  confidence={m.confidence}")

    # Step 1: accept the engine's suggestion
    print(f"\n  [1/3] accept")
    service.accept_exception(session, be_id, actor="operator",
                             note="looks plausible - accepting engine suggestion")
    session.commit()
    m = session.query(ReconciliationMatch).filter(
        ReconciliationMatch.bank_event_id == be_id).first()
    print(f"        status now: {m.status.value}")

    # Step 2: reopen - operator spots a problem
    # accept sets status=resolved; move to matched so reopen() is valid,
    # simulating what happens when an operator revisits an auto-matched item.
    m.status = ReconciliationMatchStatus.MATCHED
    session.commit()

    print(f"\n  [2/3] reopen")
    service.reopen_exception(session, be_id, actor="operator",
                             note="amount looks off on closer inspection - reopening")
    session.commit()
    m = session.query(ReconciliationMatch).filter(
        ReconciliationMatch.bank_event_id == be_id).first()
    print(f"        status now: {m.status.value}")

    # Step 3: manual match to a different ledger entry
    free_le = _any_free_ledger_entry(session, be_id)
    if not free_le:
        print("\n  No free ledger entry available for manual match - skipping step 3.")
    else:
        print(f"\n  [3/3] match -> ledger_entry {str(free_le.id)[:8]}...")
        service.match_exception(session, be_id, [free_le.id], actor="operator",
                                note="correct ledger entry identified")
        session.commit()
        m = session.query(ReconciliationMatch).filter(
            ReconciliationMatch.bank_event_id == be_id).first()
        print(f"        status now: {m.status.value}  match_type={m.match_type}")

    # After stats
    stats_after = service.get_stats(session)
    _print_stats("AFTER: queue state", stats_after)

    # Full audit trail for this bank event
    history = service.get_audit_history(session, be_id)
    print(f"\n  Audit trail for bank_event {short_id}... ({len(history)} entries)")
    print(f"  {'timestamp':<20} {'action':<12} {'before':<20} {'after':<20} note")
    print(f"  {'-'*90}")
    for entry in history:
        ts = entry["created_at"][:19]
        before_s = entry["payload"].get("before", {}).get("status", "-")
        after_s  = entry["payload"].get("after",  {}).get("status", "-")
        note     = entry["payload"].get("note", "")
        print(f"  {ts}  {entry['action']:<12} {before_s:<20} {after_s:<20} {note}")
    print()

    session.close()


if __name__ == "__main__":
    main()
