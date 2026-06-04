"""
Cash-position service.

"Cleared" is defined operationally: a ledger entry is cleared when it appears
in match_ledger_entry linked to a reconciliation_match whose status is one of
{matched, resolved, partially_resolved}.

  - needs_review entries are NOT cleared — their ledger entries remain pending
    liability until an operator confirms them.
  - partially_resolved entries ARE cleared: the ledger entry is linked to a
    confirmed bank event, even if the allocation was partial.  The full ledger
    entry amount counts once toward funded_balance and does not appear in
    pending_claims_liability (no double-count).

The ledger_entry.status column (expected/cleared) is not updated by the match
engine, so clearance is derived from the reconciliation join — the same rows
the matcher produced.

funded_balance sign convention: use the entry's own Direction field rather than
hardcoding per-type signs.  admin_fee carries Direction.CREDIT in this ledger
(the TPA records it as fee income received); claim_payment and stop_loss_premium
carry Direction.DEBIT (cash out).  Using Direction directly makes the formula
robust to seeding conventions.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.db.models import (
    Direction,
    EmployerGroup,
    LedgerEntry,
    LedgerEntryType,
    MatchLedgerEntry,
    Member,
    ReconciliationMatch,
    ReconciliationMatchStatus,
)
from backend.cash_position.schemas import (
    CashPositionResponse,
    CashPositionSummary,
    ClearedEntry,
    GroupPosition,
    GroupPositionDetail,
)

# Coverage thresholds
_WATCH_RATIO = Decimal("1.00")    # funded >= pending × 1.00 → watch (thin margin)
_HEALTHY_RATIO = Decimal("1.10")  # funded >= pending × 1.10 → healthy (10% buffer)

# Entry types included in the funded-balance and pending-liability calculations.
# Direction (CREDIT / DEBIT) is taken from ledger_entry.direction, not inferred
# from the entry type, because admin_fee is seeded as CREDIT (fee income).
_POSITION_TYPES = [
    LedgerEntryType.EMPLOYER_FUNDING,
    LedgerEntryType.STOP_LOSS_REIMBURSEMENT,
    LedgerEntryType.CLAIM_PAYMENT,
    LedgerEntryType.STOP_LOSS_PREMIUM,
    LedgerEntryType.ADMIN_FEE,
]

# Reconciliation statuses that mean "bank-confirmed / cleared"
_CLEARED_STATUSES = [
    ReconciliationMatchStatus.MATCHED,
    ReconciliationMatchStatus.RESOLVED,
    ReconciliationMatchStatus.PARTIALLY_RESOLVED,
]


def _cleared_le_subquery(session: Session):
    """Subquery returning ledger_entry_ids linked to a cleared reconciliation_match."""
    return (
        select(MatchLedgerEntry.ledger_entry_id)
        .join(
            ReconciliationMatch,
            MatchLedgerEntry.reconciliation_match_id == ReconciliationMatch.id,
        )
        .where(ReconciliationMatch.status.in_(_CLEARED_STATUSES))
        .distinct()
    )


def _coverage_status(funded: Decimal, pending: Decimal) -> str:
    if pending == Decimal("0"):
        return "healthy"
    if funded >= pending * _HEALTHY_RATIO:
        return "healthy"
    if funded >= pending * _WATCH_RATIO:
        return "watch"
    return "shortfall"


def _compute_position(session: Session, group: EmployerGroup) -> GroupPosition:
    group_id = group.id
    cleared_subq = _cleared_le_subquery(session)

    # Credits in: sum of cleared CREDIT entries among the position types
    cleared_credits = session.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0")))
        .where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.entry_type.in_(_POSITION_TYPES),
            LedgerEntry.direction == Direction.CREDIT,
            LedgerEntry.id.in_(cleared_subq),
        )
    ).scalar() or Decimal("0")

    # Debits out: sum of cleared DEBIT entries among the position types
    cleared_debits = session.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0")))
        .where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.entry_type.in_(_POSITION_TYPES),
            LedgerEntry.direction == Direction.DEBIT,
            LedgerEntry.id.in_(cleared_subq),
        )
    ).scalar() or Decimal("0")

    funded_balance = Decimal(str(cleared_credits)) - Decimal(str(cleared_debits))

    # Pending = uncleared claim_payment entries (money that needs to go out but hasn't cleared).
    # Complement of cleared, restricted to outbound claim payments.
    # Entries in needs_review / flagged / unmatched matches count as pending.
    pending_liability = session.execute(
        select(func.coalesce(func.sum(LedgerEntry.amount), Decimal("0")))
        .where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT,
            LedgerEntry.id.not_in(cleared_subq),
        )
    ).scalar() or Decimal("0")

    pending_liability = Decimal(str(pending_liability))
    available_to_cover = funded_balance

    member_count: int = session.execute(
        select(func.count(Member.id)).where(Member.group_id == group_id)
    ).scalar() or 0

    return GroupPosition(
        group_id=str(group_id),
        group_name=group.name,
        funded_balance=funded_balance,
        pending_claims_liability=pending_liability,
        available_to_cover=available_to_cover,
        coverage_status=_coverage_status(funded_balance, pending_liability),
        member_count=member_count,
    )


def _serialize_entry(le: LedgerEntry) -> ClearedEntry:
    return ClearedEntry(
        id=str(le.id),
        entry_type=le.entry_type.value if hasattr(le.entry_type, "value") else str(le.entry_type),
        direction=le.direction.value if hasattr(le.direction, "value") else str(le.direction),
        amount=Decimal(str(le.amount)),
        expected_date=le.expected_date,
        reference=le.reference,
        counterparty=le.counterparty,
        status=le.status.value if hasattr(le.status, "value") else str(le.status),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_positions(session: Session) -> CashPositionResponse:
    groups = session.execute(
        select(EmployerGroup).order_by(EmployerGroup.name)
    ).scalars().all()

    positions = [_compute_position(session, g) for g in groups]

    # Default sort: worst coverage first; secondary = funded_balance ascending
    _order = {"shortfall": 0, "watch": 1, "healthy": 2}
    positions.sort(key=lambda p: (_order[p.coverage_status], p.funded_balance))

    total_funded = sum(p.funded_balance for p in positions)
    total_pending = sum(p.pending_claims_liability for p in positions)
    groups_in_shortfall = sum(1 for p in positions if p.coverage_status == "shortfall")

    return CashPositionResponse(
        summary=CashPositionSummary(
            total_funded=total_funded,
            total_pending_liability=total_pending,
            groups_in_shortfall=groups_in_shortfall,
        ),
        groups=positions,
    )


def get_group_detail(session: Session, group_id: UUID) -> GroupPositionDetail | None:
    group = session.get(EmployerGroup, group_id)
    if group is None:
        return None

    position = _compute_position(session, group)
    cleared_subq = _cleared_le_subquery(session)

    cleared_les = session.execute(
        select(LedgerEntry)
        .where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.id.in_(cleared_subq),
        )
        .order_by(LedgerEntry.expected_date.desc())
        .limit(100)
    ).scalars().all()

    pending_les = session.execute(
        select(LedgerEntry)
        .where(
            LedgerEntry.group_id == group_id,
            LedgerEntry.entry_type == LedgerEntryType.CLAIM_PAYMENT,
            LedgerEntry.id.not_in(cleared_subq),
        )
        .order_by(LedgerEntry.expected_date.desc())
        .limit(50)
    ).scalars().all()

    return GroupPositionDetail(
        **position.model_dump(),
        cleared_entries=[_serialize_entry(le) for le in cleared_les],
        pending_entries=[_serialize_entry(le) for le in pending_les],
    )
