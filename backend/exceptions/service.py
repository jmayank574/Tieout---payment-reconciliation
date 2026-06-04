"""
Exception resolution service — business logic for the operator workflow.

All public functions accept a SQLAlchemy Session and return plain Python
dicts (or model instances for internal callers).  They call session.flush()
but never session.commit() — the caller owns the transaction boundary.

Audit contract
--------------
Every state-changing function writes exactly one AuditLog row with:
  actor      — who acted
  action     — verb: accept | match | split | write_off | flag | reopen
  entity_type — "reconciliation_match"
  entity_id   — match.id  (for direct lookup by match)
  payload     — {bank_event_id, before, after, note?}

bank_event_id is stored in every payload so that
GET /audit/{bank_event_id} can reconstruct the FULL timeline across the
life of a bank event even if match rows were ever replaced.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import (
    AuditLog,
    BankEvent,
    LedgerEntry,
    MatchLedgerEntry,
    ReconciliationMatch, ReconciliationMatchStatus,
)
from backend.match.engine import (
    FUZZY_DATE_WINDOW,
    _amount_proximity,
    _date_proximity,
    _text_similarity,
)

# Statuses that keep an item visible in the operator queue
QUEUE_STATUSES = (
    ReconciliationMatchStatus.NEEDS_REVIEW,
    ReconciliationMatchStatus.FLAGGED,
    ReconciliationMatchStatus.PARTIALLY_RESOLVED,
)

# Statuses that lock ledger entries (can't be reassigned)
LOCKED_STATUSES = (
    ReconciliationMatchStatus.RESOLVED,
    ReconciliationMatchStatus.WRITTEN_OFF,
    ReconciliationMatchStatus.PARTIALLY_RESOLVED,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_match(session: Session, bank_event_id: UUID) -> ReconciliationMatch:
    match = (
        session.query(ReconciliationMatch)
        .filter(ReconciliationMatch.bank_event_id == bank_event_id)
        .first()
    )
    if not match:
        raise ValueError(f"No reconciliation match found for bank_event_id={bank_event_id}")
    return match


def _get_bank_event(session: Session, bank_event_id: UUID) -> BankEvent:
    be = session.query(BankEvent).filter(BankEvent.id == bank_event_id).first()
    if not be:
        raise ValueError(f"BankEvent {bank_event_id} not found")
    return be


def _current_le_ids(session: Session, match_id: UUID) -> list[str]:
    rows = (
        session.query(MatchLedgerEntry)
        .filter(MatchLedgerEntry.reconciliation_match_id == match_id)
        .all()
    )
    return [str(r.ledger_entry_id) for r in rows]


def _write_audit(
    session: Session,
    actor: str,
    action: str,
    match: ReconciliationMatch,
    before: dict,
    after: dict,
    note: str | None = None,
) -> AuditLog:
    payload: dict = {
        "bank_event_id": str(match.bank_event_id),  # anchor for cross-match timeline
        "before": before,
        "after": after,
    }
    if note:
        payload["note"] = note
    log = AuditLog(
        actor=actor,
        action=action,
        entity_type="reconciliation_match",
        entity_id=match.id,
        payload=payload,
    )
    session.add(log)
    return log


def _le_to_dict(le: LedgerEntry) -> dict:
    return {
        "id": str(le.id),
        "entry_type": le.entry_type.value,
        "direction": le.direction.value,
        "amount": str(le.amount),
        "expected_date": le.expected_date.isoformat(),
        "reference": le.reference,
        "counterparty": le.counterparty,
    }


def _explain_uncertainty(
    match_type: str | None,
    confidence: Decimal | None,
    bank_event: BankEvent,
    ledger_entries: list[LedgerEntry],
) -> str:
    if match_type == "unmatched" or not ledger_entries:
        return "No ledger counterpart found — possible bank fee, interest, or genuine noise"

    le = ledger_entries[0]
    conf = float(confidence or 0)
    reasons: list[str] = []

    if match_type == "fuzzy":
        date_diff = abs((bank_event.posted_date - le.expected_date).days)
        if bank_event.amount != le.amount and le.amount:
            diff_pct = abs(bank_event.amount - le.amount) / le.amount * 100
            reasons.append(f"±{float(diff_pct):.1f}% amount variance ({bank_event.amount} vs {le.amount})")
        if date_diff > 3:
            reasons.append(f"amount matches but {date_diff} days late")
        if le.reference and le.reference.lower() not in (bank_event.descriptor or "").lower():
            reasons.append("no reference found in bank descriptor")
        if not reasons:
            reasons.append(f"low-confidence fuzzy match (score {conf:.2f})")
    elif match_type == "many_to_one":
        reasons.append("batch reference unclear — matched by amount only")
    elif match_type == "one_to_many":
        reasons.append("bank event is one of two partial payments for a single ledger entry")
    elif match_type == "reversal":
        reasons.append("part of a pay/return/reissue reversal cluster")
    else:
        reasons.append(f"low-confidence {match_type} match (score {conf:.2f})")

    return "; ".join(reasons) if reasons else f"uncertain match (confidence {conf:.2f})"


def _score_candidate(bank_event: BankEvent, le: LedgerEntry) -> tuple[float, list[str]]:
    """Score a ledger entry as a candidate match. Returns (score, reason_strings)."""
    amt_prox = _amount_proximity(le.amount, bank_event.amount)
    date_prox = _date_proximity(le.expected_date, bank_event.posted_date, FUZZY_DATE_WINDOW)
    descriptor = (bank_event.descriptor or "").lower()
    le_text = f"{le.reference or ''} {le.counterparty or ''}".lower().strip()
    text_sim = _text_similarity(le_text, descriptor) if le_text else 0.0
    score = 0.45 * amt_prox + 0.35 * date_prox + 0.20 * text_sim

    reasons: list[str] = []
    if amt_prox == 1.0:
        reasons.append("exact amount match")
    elif amt_prox > 0 and le.amount:
        diff_pct = abs(bank_event.amount - le.amount) / le.amount * 100
        reasons.append(f"±{float(diff_pct):.1f}% amount difference")
    else:
        reasons.append("amount outside tolerance")

    date_diff = abs((bank_event.posted_date - le.expected_date).days)
    if date_diff == 0:
        reasons.append("same date")
    else:
        reasons.append(f"{date_diff}d date difference")

    if text_sim > 0.5:
        reasons.append("strong descriptor match")
    elif text_sim > 0.2:
        reasons.append("partial descriptor match")

    return score, reasons


def _find_candidates(
    session: Session,
    bank_event: BankEvent,
    exclude_le_ids: set,
    limit: int = 10,
) -> list[dict]:
    """Find and score unmatched ledger entries near this bank event."""
    # Ledger entries locked into resolved/written_off/partially_resolved matches
    locked_rows = (
        session.query(MatchLedgerEntry.ledger_entry_id)
        .join(ReconciliationMatch, MatchLedgerEntry.reconciliation_match_id == ReconciliationMatch.id)
        .filter(ReconciliationMatch.status.in_(list(LOCKED_STATUSES)))
        .all()
    )
    locked_ids = [r.ledger_entry_id for r in locked_rows]

    amount_low = bank_event.amount * Decimal("0.80")
    amount_high = bank_event.amount * Decimal("1.20")
    date_low = bank_event.posted_date - timedelta(days=30)
    date_high = bank_event.posted_date + timedelta(days=30)

    q = session.query(LedgerEntry).filter(
        LedgerEntry.bank_account_id == bank_event.bank_account_id,
        LedgerEntry.direction == bank_event.direction,
        LedgerEntry.amount.between(amount_low, amount_high),
        LedgerEntry.expected_date.between(date_low, date_high),
    )
    if locked_ids:
        q = q.filter(~LedgerEntry.id.in_(locked_ids))
    q = q.limit(50)

    candidates = q.all()
    if exclude_le_ids:
        candidates = [c for c in candidates if c.id not in exclude_le_ids]

    scored = []
    for le in candidates:
        score, reasons = _score_candidate(bank_event, le)
        if score > 0:
            scored.append((score, le, reasons))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "ledger_entry": _le_to_dict(le),
            "score": round(score, 4),
            "score_reasons": reasons,
        }
        for score, le, reasons in scored[:limit]
    ]


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

def list_exceptions(
    session: Session,
    *,
    statuses: list[str] | None = None,
    match_type: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    bank_account_id: UUID | None = None,
    sort: str = "confidence_asc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Return a paginated list of exception summaries."""
    if statuses is None:
        active_statuses = [s for s in QUEUE_STATUSES]
    else:
        active_statuses = [ReconciliationMatchStatus(s) for s in statuses]

    q = (
        session.query(ReconciliationMatch, BankEvent)
        .join(BankEvent, ReconciliationMatch.bank_event_id == BankEvent.id)
        .filter(ReconciliationMatch.status.in_(active_statuses))
    )

    if match_type:
        q = q.filter(ReconciliationMatch.match_type == match_type)
    if bank_account_id:
        q = q.filter(BankEvent.bank_account_id == bank_account_id)
    if amount_min is not None:
        q = q.filter(BankEvent.amount >= amount_min)
    if amount_max is not None:
        q = q.filter(BankEvent.amount <= amount_max)

    total = q.count()

    if sort == "amount_desc":
        q = q.order_by(BankEvent.amount.desc())
    elif sort == "date_asc":
        q = q.order_by(BankEvent.posted_date.asc())
    else:  # confidence_asc — worst first
        q = q.order_by(ReconciliationMatch.confidence.asc().nullsfirst())

    offset = (page - 1) * page_size
    rows = q.offset(offset).limit(page_size).all()

    return {
        "items": [
            {
                "bank_event_id": str(rm.bank_event_id),
                "match_id": str(rm.id),
                "posted_date": be.posted_date.isoformat(),
                "amount": str(be.amount),
                "direction": be.direction.value,
                "descriptor": be.descriptor,
                "bank_account_id": str(be.bank_account_id),
                "match_type": rm.match_type,
                "confidence": str(rm.confidence) if rm.confidence is not None else None,
                "status": rm.status.value,
            }
            for rm, be in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_exception_detail(session: Session, bank_event_id: UUID) -> dict:
    """Full detail for one exception: bank event, suggestion, why-uncertain, candidates."""
    match = _get_match(session, bank_event_id)
    be = _get_bank_event(session, bank_event_id)

    mle_rows = (
        session.query(MatchLedgerEntry)
        .filter(MatchLedgerEntry.reconciliation_match_id == match.id)
        .all()
    )
    suggested_le_ids = {r.ledger_entry_id for r in mle_rows}
    allocated = {r.ledger_entry_id: r.allocated_amount for r in mle_rows}
    suggested_les = (
        session.query(LedgerEntry).filter(LedgerEntry.id.in_(suggested_le_ids)).all()
        if suggested_le_ids else []
    )

    suggested_dicts = []
    for le in suggested_les:
        d = _le_to_dict(le)
        if allocated.get(le.id) is not None:
            d["allocated_amount"] = str(allocated[le.id])
        suggested_dicts.append(d)

    why = _explain_uncertainty(match.match_type, match.confidence, be, suggested_les)
    candidates = _find_candidates(session, be, suggested_le_ids)

    return {
        "bank_event_id": str(bank_event_id),
        "match_id": str(match.id),
        "bank_event": {
            "id": str(be.id),
            "amount": str(be.amount),
            "posted_date": be.posted_date.isoformat(),
            "descriptor": be.descriptor,
            "direction": be.direction.value,
            "bank_reference": be.bank_reference,
            "bank_account_id": str(be.bank_account_id),
        },
        "match_type": match.match_type,
        "confidence": str(match.confidence) if match.confidence is not None else None,
        "status": match.status.value,
        "why_uncertain": why,
        "suggested_ledger_entries": suggested_dicts,
        "candidates": candidates,
        "notes": match.notes,
        "resolved_by": match.resolved_by,
        "resolved_at": match.resolved_at.isoformat() if match.resolved_at else None,
    }


def get_audit_history(session: Session, bank_event_id: UUID) -> list[dict]:
    """Return full audit timeline for a bank event, ordered oldest-first.

    Queries the JSONB payload for bank_event_id so the timeline spans all
    match rows a bank event may have had across its lifecycle.
    """
    rows = (
        session.query(AuditLog)
        .filter(
            AuditLog.entity_type == "reconciliation_match",
            AuditLog.payload["bank_event_id"].astext == str(bank_event_id),
        )
        .order_by(AuditLog.created_at.asc())
        .all()
    )
    return [
        {
            "id": str(r.id),
            "actor": r.actor,
            "action": r.action,
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id) if r.entity_id else None,
            "created_at": r.created_at.isoformat(),
            "payload": r.payload,
        }
        for r in rows
    ]


def get_stats(session: Session) -> dict:
    """Queue health numbers: counts by status, unresolved dollars, oldest age."""
    by_status: dict[str, int] = {}
    for status in ReconciliationMatchStatus:
        count = (
            session.query(func.count(ReconciliationMatch.id))
            .filter(ReconciliationMatch.status == status)
            .scalar() or 0
        )
        by_status[status.value] = count

    unresolved_amount = (
        session.query(func.sum(BankEvent.amount))
        .join(ReconciliationMatch, ReconciliationMatch.bank_event_id == BankEvent.id)
        .filter(ReconciliationMatch.status.in_(list(QUEUE_STATUSES)))
        .scalar() or Decimal("0")
    )

    oldest_date: date | None = (
        session.query(func.min(BankEvent.posted_date))
        .join(ReconciliationMatch, ReconciliationMatch.bank_event_id == BankEvent.id)
        .filter(ReconciliationMatch.status.in_(list(QUEUE_STATUSES)))
        .scalar()
    )
    oldest_days = (date.today() - oldest_date).days if oldest_date else None

    return {
        "by_status": by_status,
        "total_unresolved_amount": str(unresolved_amount),
        "oldest_unresolved_days": oldest_days,
        "total_exceptions": sum(by_status.values()),
    }


# ---------------------------------------------------------------------------
# Resolution actions
# ---------------------------------------------------------------------------

def accept_exception(
    session: Session,
    bank_event_id: UUID,
    actor: str = "operator",
    note: str | None = None,
) -> dict:
    """Accept the engine's suggested match. Idempotent when already resolved."""
    match = _get_match(session, bank_event_id)

    if match.status == ReconciliationMatchStatus.RESOLVED:
        return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
                "new_status": match.status.value, "action": "accept", "idempotent": True}

    if match.status not in QUEUE_STATUSES:
        raise ValueError(
            f"Cannot accept: match status is '{match.status.value}' "
            f"(must be one of {[s.value for s in QUEUE_STATUSES]})"
        )

    before = {
        "status": match.status.value,
        "match_type": match.match_type,
        "ledger_entry_ids": _current_le_ids(session, match.id),
    }

    match.status = ReconciliationMatchStatus.RESOLVED
    match.resolved_by = actor
    match.resolved_at = datetime.now(timezone.utc)
    if note:
        match.notes = note

    after = {
        "status": match.status.value,
        "match_type": match.match_type,
        "ledger_entry_ids": _current_le_ids(session, match.id),
    }

    _write_audit(session, actor, "accept", match, before, after, note)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": match.status.value, "action": "accept"}


def match_exception(
    session: Session,
    bank_event_id: UUID,
    ledger_entry_ids: list[UUID],
    actor: str = "operator",
    note: str | None = None,
) -> dict:
    """Manually assign ledger entries to a bank event. Replaces any existing assignment."""
    match = _get_match(session, bank_event_id)

    for le_id in ledger_entry_ids:
        if not session.query(LedgerEntry).filter(LedgerEntry.id == le_id).first():
            raise ValueError(f"LedgerEntry {le_id} not found")

    before = {
        "status": match.status.value,
        "match_type": match.match_type,
        "ledger_entry_ids": _current_le_ids(session, match.id),
    }

    session.query(MatchLedgerEntry).filter(
        MatchLedgerEntry.reconciliation_match_id == match.id
    ).delete(synchronize_session="fetch")
    for le_id in ledger_entry_ids:
        session.add(MatchLedgerEntry(
            id=uuid4(),
            reconciliation_match_id=match.id,
            ledger_entry_id=le_id,
        ))
    session.flush()

    match.match_type = "manual"
    match.status = ReconciliationMatchStatus.RESOLVED
    match.resolved_by = actor
    match.resolved_at = datetime.now(timezone.utc)
    if note:
        match.notes = note

    after = {
        "status": match.status.value,
        "match_type": match.match_type,
        "ledger_entry_ids": [str(i) for i in ledger_entry_ids],
    }

    _write_audit(session, actor, "match", match, before, after, note)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": match.status.value, "action": "match"}


def split_exception(
    session: Session,
    bank_event_id: UUID,
    allocations: list[dict],
    actor: str = "operator",
    note: str | None = None,
) -> dict:
    """
    Resolve a bank event by splitting it across multiple ledger entries.

    allocations: list of {"ledger_entry_id": UUID, "allocated_amount": Decimal}

    - sum == bank amount → status = resolved/split
    - sum <  bank amount → status = partially_resolved/split (remainder tracked)
    - sum >  bank amount → ValueError (reject)
    """
    match = _get_match(session, bank_event_id)
    be = _get_bank_event(session, bank_event_id)

    total = Decimal("0")
    for a in allocations:
        amt = Decimal(str(a["allocated_amount"]))
        if amt <= 0:
            raise ValueError(f"allocated_amount must be positive, got {amt}")
        total += amt

    if total > be.amount:
        raise ValueError(
            f"Allocations sum {total} exceeds bank event amount {be.amount} — "
            "cannot allocate money that isn't there"
        )

    for a in allocations:
        if not session.query(LedgerEntry).filter(LedgerEntry.id == a["ledger_entry_id"]).first():
            raise ValueError(f"LedgerEntry {a['ledger_entry_id']} not found")

    remainder = be.amount - total
    is_partial = remainder > Decimal("0")

    before = {
        "status": match.status.value,
        "match_type": match.match_type,
        "ledger_entry_ids": _current_le_ids(session, match.id),
    }

    session.query(MatchLedgerEntry).filter(
        MatchLedgerEntry.reconciliation_match_id == match.id
    ).delete(synchronize_session="fetch")
    for a in allocations:
        session.add(MatchLedgerEntry(
            id=uuid4(),
            reconciliation_match_id=match.id,
            ledger_entry_id=a["ledger_entry_id"],
            allocated_amount=Decimal(str(a["allocated_amount"])),
        ))
    session.flush()

    match.match_type = "split"
    match.resolved_by = actor
    match.resolved_at = datetime.now(timezone.utc)

    if is_partial:
        match.status = ReconciliationMatchStatus.PARTIALLY_RESOLVED
        remainder_note = f"Partial split: {remainder} unallocated of {be.amount} bank amount"
        match.notes = f"{remainder_note}{'; ' + note if note else ''}"
        new_status = ReconciliationMatchStatus.PARTIALLY_RESOLVED.value
    else:
        match.status = ReconciliationMatchStatus.RESOLVED
        if note:
            match.notes = note
        new_status = ReconciliationMatchStatus.RESOLVED.value

    after = {
        "status": new_status,
        "match_type": "split",
        "allocations": [
            {
                "ledger_entry_id": str(a["ledger_entry_id"]),
                "allocated_amount": str(Decimal(str(a["allocated_amount"]))),
            }
            for a in allocations
        ],
        "remainder": str(remainder),
    }

    _write_audit(session, actor, "split", match, before, after, note)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": new_status, "action": "split", "remainder": str(remainder)}


def write_off_exception(
    session: Session,
    bank_event_id: UUID,
    reason: str,
    actor: str = "operator",
) -> dict:
    """Declare no ledger counterpart exists. Idempotent when already written off."""
    match = _get_match(session, bank_event_id)

    if match.status == ReconciliationMatchStatus.WRITTEN_OFF:
        return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
                "new_status": match.status.value, "action": "write_off", "idempotent": True}

    before = {"status": match.status.value, "match_type": match.match_type}

    match.status = ReconciliationMatchStatus.WRITTEN_OFF
    match.resolved_by = actor
    match.resolved_at = datetime.now(timezone.utc)
    match.notes = reason

    after = {"status": match.status.value, "reason": reason}

    _write_audit(session, actor, "write_off", match, before, after, reason)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": match.status.value, "action": "write_off"}


def flag_exception(
    session: Session,
    bank_event_id: UUID,
    note: str,
    actor: str = "operator",
) -> dict:
    """Escalate / mark for follow-up. Stays in the queue as flagged."""
    match = _get_match(session, bank_event_id)

    before = {"status": match.status.value}

    match.status = ReconciliationMatchStatus.FLAGGED
    match.notes = note

    after = {"status": match.status.value, "note": note}

    _write_audit(session, actor, "flag", match, before, after, note)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": match.status.value, "action": "flag"}


def reopen_exception(
    session: Session,
    bank_event_id: UUID,
    actor: str = "operator",
    note: str | None = None,
) -> dict:
    """Move an auto-matched item back into the needs_review queue.

    Only valid for status=matched. Idempotent when already needs_review.
    Raises ValueError for any other status.
    """
    match = _get_match(session, bank_event_id)

    if match.status == ReconciliationMatchStatus.NEEDS_REVIEW:
        return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
                "new_status": match.status.value, "action": "reopen", "idempotent": True}

    if match.status != ReconciliationMatchStatus.MATCHED:
        raise ValueError(
            f"reopen requires status=matched, current status='{match.status.value}'"
        )

    before = {"status": match.status.value}

    match.status = ReconciliationMatchStatus.NEEDS_REVIEW
    match.resolved_by = None
    match.resolved_at = None
    if note:
        match.notes = note

    after = {"status": match.status.value}

    _write_audit(session, actor, "reopen", match, before, after, note)
    session.flush()
    return {"bank_event_id": str(bank_event_id), "match_id": str(match.id),
            "new_status": match.status.value, "action": "reopen"}
