"""
Print a summary of the database: row counts, money totals, per-group positions, exceptions.
Run with: python backend/scripts/summary.py
"""

from decimal import Decimal
from sqlalchemy import func, distinct
from backend.db.connection import SessionLocal
from backend.db.models import (
    EmployerGroup, Member, BankAccount, Claim, PaymentBatch,
    LedgerEntry, BankEvent, GroundTruthLink,
    Direction, ExceptionType
)
from backend.config import EXCEPTION_MIX


def get_summary():
    """Fetch and compute summary statistics."""
    session = SessionLocal()
    try:
        summary = {}
        
        # Row counts
        summary["row_counts"] = {
            "employer_groups": session.query(EmployerGroup).count(),
            "members": session.query(Member).count(),
            "bank_accounts": session.query(BankAccount).count(),
            "claims": session.query(Claim).count(),
            "payment_batches": session.query(PaymentBatch).count(),
            "ledger_entries": session.query(LedgerEntry).count(),
            "bank_events": session.query(BankEvent).count(),
            "ground_truth_links": session.query(GroundTruthLink).count(),
        }
        
        # Money totals
        ledger_debits = session.query(
            func.sum(LedgerEntry.amount)
        ).filter(LedgerEntry.direction == Direction.DEBIT).scalar() or Decimal(0)
        
        ledger_credits = session.query(
            func.sum(LedgerEntry.amount)
        ).filter(LedgerEntry.direction == Direction.CREDIT).scalar() or Decimal(0)
        
        bank_debits = session.query(
            func.sum(BankEvent.amount)
        ).filter(BankEvent.direction == Direction.DEBIT).scalar() or Decimal(0)
        
        bank_credits = session.query(
            func.sum(BankEvent.amount)
        ).filter(BankEvent.direction == Direction.CREDIT).scalar() or Decimal(0)
        
        summary["ledger_totals"] = {
            "debits": float(ledger_debits),
            "credits": float(ledger_credits),
            "net": float(ledger_credits - ledger_debits),
        }
        
        summary["bank_totals"] = {
            "debits": float(bank_debits),
            "credits": float(bank_credits),
            "net": float(bank_credits - bank_debits),
        }
        
        # Per-group cash position
        summary["group_positions"] = {}
        for group in session.query(EmployerGroup).all():
            group_credits = session.query(
                func.sum(LedgerEntry.amount)
            ).filter(
                LedgerEntry.group_id == group.id,
                LedgerEntry.direction == Direction.CREDIT
            ).scalar() or Decimal(0)
            
            group_debits = session.query(
                func.sum(LedgerEntry.amount)
            ).filter(
                LedgerEntry.group_id == group.id,
                LedgerEntry.direction == Direction.DEBIT
            ).scalar() or Decimal(0)
            
            summary["group_positions"][group.name] = {
                "credits": float(group_credits),
                "debits": float(group_debits),
                "position": float(group_credits - group_debits),
            }
        
        # Exception distribution (target vs realized)
        summary["exception_mix"] = {
            "target": EXCEPTION_MIX,
            "realized": {}
        }
        
        # Proportions are by COUNT OF BANK EVENTS (distinct bank_event_id per type),
        # not by link count. This normalises many_to_one correctly: each batch is
        # one bank event even though it generates N links.
        total_bank_events = session.query(BankEvent).count()
        if total_bank_events > 0:
            for ex_type in ExceptionType:
                be_count = session.query(
                    func.count(distinct(GroundTruthLink.bank_event_id))
                ).filter(
                    GroundTruthLink.exception_type == ex_type
                ).scalar() or 0
                summary["exception_mix"]["realized"][ex_type.value] = {
                    "count": be_count,
                    "proportion": be_count / total_bank_events,
                }
        
        # Sanity checks
        summary["sanity_checks"] = {
            "batch_totals_match": _check_batch_totals(session),
            "every_bank_event_has_ground_truth": _check_bank_events_have_links(session),
            "bank_only_noise_has_no_ledger": _check_noise_entries(session),
        }
        
        return summary
        
    finally:
        session.close()


def _check_batch_totals(session) -> bool:
    """Verify that each payment_batch total equals sum of its claims."""
    batches = session.query(PaymentBatch).all()
    for batch in batches:
        claim_sum = session.query(
            func.sum(Claim.paid_amount)
        ).filter(Claim.payment_batch_id == batch.id).scalar() or Decimal(0)
        
        if Decimal(str(batch.total_amount)) != claim_sum:
            return False
    return True


def _check_bank_events_have_links(session) -> bool:
    """Verify that every bank_event has at least one ground_truth_link."""
    unlinked = session.query(BankEvent).filter(
        ~BankEvent.id.in_(
            session.query(GroundTruthLink.bank_event_id).distinct()
        )
    ).count()
    return unlinked == 0


def _check_noise_entries(session) -> bool:
    """Verify that bank_only_noise entries have NULL ledger_entry_id."""
    bad_noise = session.query(GroundTruthLink).filter(
        GroundTruthLink.exception_type == ExceptionType.BANK_ONLY_NOISE,
        GroundTruthLink.ledger_entry_id.isnot(None)
    ).count()
    return bad_noise == 0


def print_summary():
    """Print a formatted summary."""
    summary = get_summary()
    
    print("\n" + "=" * 70)
    print("TIEOUT DATABASE SUMMARY")
    print("=" * 70)
    
    print("\nRow Counts:")
    for table, count in summary["row_counts"].items():
        print(f"  {table:25s}: {count:6d}")
    
    print("\nLedger Totals (Book):")
    print(f"  Debits:  ${summary['ledger_totals']['debits']:>12.2f}")
    print(f"  Credits: ${summary['ledger_totals']['credits']:>12.2f}")
    print(f"  Net:     ${summary['ledger_totals']['net']:>12.2f}")
    
    print("\nBank Totals (Posted):")
    print(f"  Debits:  ${summary['bank_totals']['debits']:>12.2f}")
    print(f"  Credits: ${summary['bank_totals']['credits']:>12.2f}")
    print(f"  Net:     ${summary['bank_totals']['net']:>12.2f}")
    
    print("\nPer-Group Cash Position:")
    for group_name, position in summary["group_positions"].items():
        print(f"  {group_name:35s}: ${position['position']:>12.2f}")
    
    print("\nException Mix (Target vs Realized)  [by bank event count]:")
    print(f"  {'Exception Type':30s} {'Target':>10s} {'Realized':>10s}")
    print(f"  {'-' * 50}")
    for ex_type in ExceptionType:
        target_pct = summary["exception_mix"]["target"].get(ex_type.value, 0) * 100
        realized = summary["exception_mix"]["realized"].get(ex_type.value, {})
        realized_pct = realized.get("proportion", 0) * 100
        realized_count = realized.get("count", 0)
        print(f"  {ex_type.value:30s} {target_pct:>9.1f}% {realized_pct:>9.1f}% ({realized_count:4d})")
    
    print("\nSanity Checks:")
    for check_name, passed in summary["sanity_checks"].items():
        status = "PASS" if passed else "FAIL"
        print(f"  {check_name:40s}: {status}")
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    print_summary()
