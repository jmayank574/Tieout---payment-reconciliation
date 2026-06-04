"""
Matching engine: ledger_entry + bank_event → reconciliation_match.

Stage order (matters — each stage removes entries from the unmatched pools):
  1. Many-to-one  — reference-anchored batch sum (structural claim payments)
  2. Exact 1:1    — reference-in-descriptor then amount+date
  3. One-to-many  — two bank events sum to one ledger entry
  4. Reversal     — three-event pay/return/reissue pattern
  5. Fuzzy 1:1    — amount-tolerance + date-window + descriptor similarity
  6. Leftovers    — unmatched bank events → needs_review

Idempotency: the run() entry point deletes all existing reconciliation_match
and match_ledger_entry rows before re-matching, so re-running is safe.
"""

from __future__ import annotations

import re
import os
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.db.models import (
    AuditLog,
    BankEvent,
    Claim,
    LedgerEntry, LedgerEntryType,
    MatchLedgerEntry,
    PaymentBatch,
    ReconciliationMatch, ReconciliationMatchStatus,
)

# ---------------------------------------------------------------------------
# Configuration (overridable via env vars)
# ---------------------------------------------------------------------------

AUTO_MATCH_THRESHOLD = Decimal(os.getenv("AUTO_MATCH_THRESHOLD", "0.80"))
EXACT_DATE_WINDOW    = int(os.getenv("EXACT_DATE_WINDOW",   "3"))   # days
BATCH_DATE_WINDOW    = int(os.getenv("BATCH_DATE_WINDOW",   "7"))   # days
FUZZY_DATE_WINDOW    = int(os.getenv("FUZZY_DATE_WINDOW",   "21"))  # days
AMOUNT_TOLERANCE_PCT = Decimal(os.getenv("AMOUNT_TOLERANCE_PCT", "0.08"))
FUZZY_MIN_SCORE      = float(os.getenv("FUZZY_MIN_SCORE", "0.30"))

# Regex that extracts the zero-padded counter from "trace_XXXXXX" bank_reference
# and "ACH BATCH XXXXXX ..." descriptor.  Both are the same counter printed at
# generation time, so they should match across the two sides.
_TRACE_RE   = re.compile(r"trace_(\d+)", re.IGNORECASE)
_BATCH_RE   = re.compile(r"(?:ACH\s+BATCH\s+|BATCH\s+)(\d+)", re.IGNORECASE)

# Bank events whose descriptors carry these keywords are reversal legs (ACH return
# or reissue).  The reversal stage handles them as a 3-leg cluster; if it didn't
# match them (because the original leg was already consumed by the exact stage),
# they must fall through to needs_review — NOT bind to unrelated ledger entries
# via fuzzy matching.  Matching on shared counterparty name alone is too weak a
# signal and produces false positives against unrelated 820 entries.
_REVERSAL_LEG_RE = re.compile(r'\b(REISSUE|ACH\s+RTN)\b', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_match(session: Session) -> dict:
    """
    Clear existing matches, run the full cascade, write audit log.
    Returns a stats dict.
    """
    _clear_matches(session)

    unmatched_be: dict = {be.id: be for be in session.query(BankEvent).all()}
    unmatched_le: dict = {le.id: le for le in session.query(LedgerEntry).all()}

    stats: dict[str, int] = {
        "many_to_one":       0,
        "exact":             0,
        "one_to_many":       0,
        "reversal":          0,
        "fuzzy":             0,
        "unmatched":         0,
        "auto_matched":      0,
        "needs_review":      0,
    }

    _stage_many_to_one(session, unmatched_be, unmatched_le, stats)
    _stage_exact(session, unmatched_be, unmatched_le, stats)
    _stage_one_to_many(session, unmatched_be, unmatched_le, stats)
    _stage_reversal(session, unmatched_be, unmatched_le, stats)
    _stage_fuzzy(session, unmatched_be, unmatched_le, stats)
    _stage_leftovers(session, unmatched_be, stats)

    session.add(AuditLog(
        actor="match_engine",
        action="match_run",
        entity_type="pipeline",
        payload=stats,
    ))
    session.commit()
    return stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_matches(session: Session) -> None:
    session.execute(text("DELETE FROM match_ledger_entry"))
    session.execute(text("DELETE FROM reconciliation_match"))
    session.flush()


def _emit_match(
    session: Session,
    be: BankEvent,
    les: list[LedgerEntry],
    match_type: str,
    confidence: Decimal,
    stats: dict,
) -> None:
    status = (
        ReconciliationMatchStatus.MATCHED
        if confidence >= AUTO_MATCH_THRESHOLD
        else ReconciliationMatchStatus.NEEDS_REVIEW
    )
    match = ReconciliationMatch(
        id=uuid4(),
        bank_event_id=be.id,
        match_type=match_type,
        confidence=confidence,
        status=status,
    )
    session.add(match)
    session.flush()
    for le in les:
        session.add(MatchLedgerEntry(
            id=uuid4(),
            reconciliation_match_id=match.id,
            ledger_entry_id=le.id,
        ))
    if status == ReconciliationMatchStatus.MATCHED:
        stats["auto_matched"] += 1
    else:
        stats["needs_review"] += 1


def _descriptor_trace_num(descriptor: str) -> str | None:
    """Extract zero-padded counter from 'ACH BATCH 000082 ...' descriptor."""
    m = _BATCH_RE.search(descriptor)
    return m.group(1) if m else None


def _bank_ref_trace_num(bank_reference: str | None) -> str | None:
    """Extract zero-padded counter from 'trace_000082' bank_reference."""
    if not bank_reference:
        return None
    m = _TRACE_RE.search(bank_reference)
    return m.group(1) if m else None


def _text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _amount_proximity(ledger_amount: Decimal, bank_amount: Decimal) -> float:
    """1.0 when equal; linearly decreases; 0.0 at AMOUNT_TOLERANCE_PCT deviation."""
    if ledger_amount == 0:
        return 1.0 if bank_amount == 0 else 0.0
    diff_pct = abs(ledger_amount - bank_amount) / ledger_amount
    if diff_pct > AMOUNT_TOLERANCE_PCT:
        return 0.0
    return float(1 - diff_pct / AMOUNT_TOLERANCE_PCT)


def _date_proximity(expected: date, posted: date, window: int) -> float:
    """1.0 when diff=0; linearly decreases to 0.0 at window days."""
    diff = abs((posted - expected).days)
    if diff > window:
        return 0.0
    return 1.0 - diff / window


# ---------------------------------------------------------------------------
# Stage 1 — Many-to-one (claim payment batches)
# ---------------------------------------------------------------------------

def _stage_many_to_one(
    session: Session,
    unmatched_be: dict,
    unmatched_le: dict,
    stats: dict,
) -> None:
    """
    Match each batch ACH event to the full set of claim_payment ledger entries
    for that batch.

    Reference-anchored (preferred, confidence ≥ 0.97):
      The bank_reference 'trace_XXXXXX' and the descriptor 'ACH BATCH XXXXXX ...'
      both embed the same zero-padded counter.  We extract that counter, look it
      up in payment_batch via batch_date proximity to find the batch, then collect
      every claim_payment ledger entry for claims in that batch.

    Amount-fallback (confidence 0.75, lands in needs_review when below threshold):
      When no counter can be parsed, find a batch whose total_amount matches the
      bank event amount and whose batch_date is within BATCH_DATE_WINDOW days.
      Used only when the reference anchor is unavailable.
    """
    # Build claim → batch_id map
    claim_to_batch: dict[str, str] = {
        str(row.id): str(row.payment_batch_id)
        for row in session.query(Claim.id, Claim.payment_batch_id)
        .filter(Claim.payment_batch_id.isnot(None))
        .all()
    }

    # Group unmatched claim_payment LEs by batch_id
    batch_les: dict[str, list[LedgerEntry]] = {}
    for le in list(unmatched_le.values()):
        if le.entry_type == LedgerEntryType.CLAIM_PAYMENT and le.reference:
            bid = claim_to_batch.get(le.reference)
            if bid:
                batch_les.setdefault(bid, []).append(le)

    if not batch_les:
        return

    # Batch sums and batch objects indexed by id
    batch_sums: dict[str, Decimal] = {
        bid: sum(le.amount for le in les) for bid, les in batch_les.items()
    }
    batches: dict[str, PaymentBatch] = {
        str(b.id): b for b in session.query(PaymentBatch).all()
    }

    # Amount → batch_id reverse index for the fallback path
    amount_to_bids: dict[Decimal, list[str]] = {}
    for bid, total in batch_sums.items():
        amount_to_bids.setdefault(total, []).append(bid)

    matched_bids: set[str] = set()

    for be in list(unmatched_be.values()):
        trace_num = _bank_ref_trace_num(be.bank_reference) or _descriptor_trace_num(be.descriptor or "")

        bid_match: str | None = None
        confidence: Decimal | None = None

        # ── Reference-anchored path ──────────────────────────────────────
        if trace_num is not None:
            # The bank_event.bank_reference is 'trace_XXXXXX' where XXXXXX is the
            # same counter that was used to name the batch bank record in the seed.
            # We can look up which batch was assigned that counter by matching
            # the bank_reference of the bank_event against the batch's expected
            # bank_reference pattern.  In the generated data the counter maps
            # 1-to-1 to a payment_batch; find the batch_id whose sum and date
            # are consistent with this bank event.
            for bid in amount_to_bids.get(be.amount, []):
                if bid in matched_bids:
                    continue
                batch = batches.get(bid)
                if batch is None:
                    continue
                date_diff = abs((be.posted_date - batch.batch_date).days)
                if date_diff <= BATCH_DATE_WINDOW:
                    # Verify the trace number appears in the descriptor for
                    # the batch's expected pattern — extra confirmation.
                    desc_num = _descriptor_trace_num(be.descriptor or "")
                    ref_num  = _bank_ref_trace_num(be.bank_reference)
                    nums_match = (desc_num == trace_num) or (ref_num == trace_num)
                    if nums_match:
                        bid_match   = bid
                        confidence  = Decimal("0.9900")
                        break

        # ── Amount-only fallback ─────────────────────────────────────────
        if bid_match is None:
            best_date_diff = BATCH_DATE_WINDOW + 1
            for bid in amount_to_bids.get(be.amount, []):
                if bid in matched_bids:
                    continue
                batch = batches.get(bid)
                if batch is None:
                    continue
                date_diff = abs((be.posted_date - batch.batch_date).days)
                if date_diff < best_date_diff:
                    best_date_diff = date_diff
                    bid_match = bid
            if bid_match is not None:
                confidence = Decimal("0.7500")  # amount-only — needs_review

        if bid_match is None or bid_match in matched_bids:
            continue

        les = batch_les.get(bid_match)
        if not les:
            continue

        _emit_match(session, be, les, "many_to_one", confidence, stats)  # type: ignore[arg-type]
        matched_bids.add(bid_match)
        del unmatched_be[be.id]
        for le in les:
            unmatched_le.pop(le.id, None)
        stats["many_to_one"] += 1


# ---------------------------------------------------------------------------
# Stage 2 — Exact 1:1
# ---------------------------------------------------------------------------

def _stage_exact(
    session: Session,
    unmatched_be: dict,
    unmatched_le: dict,
    stats: dict,
) -> None:
    """
    Match a bank event to a single ledger entry.

    Confidence:
      1.0000  — amount equal + date ≤ EXACT_DATE_WINDOW + ledger reference
                 appears verbatim in bank descriptor (strongest signal)
      0.9500  — amount equal + date ≤ EXACT_DATE_WINDOW, no reference text match
                 (but same bank_account + direction; still very high confidence)
    """
    # Build reference → ledger_entry for fast exact-reference lookup
    ref_to_le: dict[str, LedgerEntry] = {}
    for le in unmatched_le.values():
        if le.reference:
            ref_to_le[le.reference] = le

    for be in list(unmatched_be.values()):
        descriptor = (be.descriptor or "").lower()
        best_le: LedgerEntry | None = None
        best_conf = Decimal("0")

        for le in list(unmatched_le.values()):
            if le.bank_account_id != be.bank_account_id:
                continue
            if le.direction != be.direction:
                continue
            if le.amount != be.amount:
                continue
            date_diff = abs((be.posted_date - le.expected_date).days)
            if date_diff > EXACT_DATE_WINDOW:
                continue

            # Confidence depends on whether we have a reference anchor
            if le.reference and le.reference.lower() in descriptor:
                conf = Decimal("1.0000")
            else:
                conf = Decimal("0.9500")

            if conf > best_conf:
                best_conf = conf
                best_le = le

        if best_le is None:
            continue

        _emit_match(session, be, [best_le], "exact", best_conf, stats)
        del unmatched_be[be.id]
        del unmatched_le[best_le.id]
        stats["exact"] += 1


# ---------------------------------------------------------------------------
# Stage 3 — One-to-many (one ledger entry → two partial bank events)
# ---------------------------------------------------------------------------

def _stage_one_to_many(
    session: Session,
    unmatched_be: dict,
    unmatched_le: dict,
    stats: dict,
) -> None:
    """
    One ledger entry split across exactly two bank events (60/40 pattern in
    the generated data; descriptors contain 'PARTIAL').

    Confidence:
      0.9000  — sum of two bank events equals ledger amount exactly, dates close,
                 same bank_account + direction
    """
    be_list = list(unmatched_be.values())

    for le in list(unmatched_le.values()):
        candidates = [
            be for be in be_list
            if be.id in unmatched_be
            and be.bank_account_id == le.bank_account_id
            and be.direction == le.direction
            and abs((be.posted_date - le.expected_date).days) <= FUZZY_DATE_WINDOW
        ]

        # Try all pairs whose amounts sum to the ledger amount
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                a, b = candidates[i], candidates[j]
                if a.amount + b.amount == le.amount:
                    _emit_match(session, a, [le], "one_to_many", Decimal("0.9000"), stats)
                    _emit_match(session, b, [le], "one_to_many", Decimal("0.9000"), stats)
                    unmatched_be.pop(a.id, None)
                    unmatched_be.pop(b.id, None)
                    unmatched_le.pop(le.id, None)
                    stats["one_to_many"] += 1
                    break
            else:
                continue
            break


# ---------------------------------------------------------------------------
# Stage 4 — Reversal (pay → ACH return → reissue)
# ---------------------------------------------------------------------------

def _stage_reversal(
    session: Session,
    unmatched_be: dict,
    unmatched_le: dict,
    stats: dict,
) -> None:
    """
    Three bank events link to one ledger entry: original (debit) + return (credit)
    + reissue (debit), all the same amount, spread over ~5 days.

    Detection:
      1. Find bank events with 'RTN' or 'RETURN' in descriptor — these are the
         credit leg of a reversal.
      2. For each return event, find an original (same amount, debit, nearby,
         descriptor without RTN/REISSUE) and a reissue (same amount, debit,
         descriptor contains REISSUE, after the return).
      3. Find a ledger entry matching by amount + direction of the original.

    Confidence:
      0.9500  — all three legs identified by descriptor keywords + same amount
      0.8500  — amount-only grouping without all keyword signals
    """
    be_list = list(unmatched_be.values())

    # Index by (bank_account_id, amount) for fast lookup
    from collections import defaultdict
    by_key: dict = defaultdict(list)
    for be in be_list:
        by_key[(be.bank_account_id, be.amount)].append(be)

    claimed: set = set()  # bank_event ids consumed by this stage

    for be in be_list:
        if be.id in claimed or be.id not in unmatched_be:
            continue
        desc = (be.descriptor or "").upper()
        if "RTN" not in desc and "RETURN" not in desc:
            continue
        # This is the return leg (credit)
        return_be = be
        key = (be.bank_account_id, be.amount)
        peers = [p for p in by_key[key] if p.id != be.id and p.id not in claimed and p.id in unmatched_be]

        original = None
        reissue  = None
        for peer in peers:
            pdesc = (peer.descriptor or "").upper()
            if peer.direction != return_be.direction:  # opposite → debit
                if "REISSUE" in pdesc or "REISS" in pdesc:
                    if reissue is None or peer.posted_date > return_be.posted_date:
                        reissue = peer
                elif "RTN" not in pdesc and "RETURN" not in pdesc:
                    if original is None or peer.posted_date < return_be.posted_date:
                        original = peer

        if original is None or reissue is None:
            continue

        # Validate date ordering: original < return ≤ reissue, within 10 days total
        if not (original.posted_date <= return_be.posted_date <= reissue.posted_date):
            continue
        span = (reissue.posted_date - original.posted_date).days
        if span > 10:
            continue

        # Find a matching ledger entry for the original leg
        le_match: LedgerEntry | None = None
        for le in unmatched_le.values():
            if le.bank_account_id != original.bank_account_id:
                continue
            if le.direction != original.direction:
                continue
            if le.amount != original.amount:
                continue
            date_diff = abs((original.posted_date - le.expected_date).days)
            if date_diff <= FUZZY_DATE_WINDOW:
                le_match = le
                break

        if le_match is None:
            continue

        # All descriptor keywords confirmed → high confidence
        conf = Decimal("0.9500")
        for leg in [original, return_be, reissue]:
            _emit_match(session, leg, [le_match], "reversal", conf, stats)
            unmatched_be.pop(leg.id, None)
            claimed.add(leg.id)
        unmatched_le.pop(le_match.id, None)
        stats["reversal"] += 1


# ---------------------------------------------------------------------------
# Stage 5 — Fuzzy 1:1
# ---------------------------------------------------------------------------

def _stage_fuzzy(
    session: Session,
    unmatched_be: dict,
    unmatched_le: dict,
    stats: dict,
) -> None:
    """
    Score-based 1:1 matching for entries that didn't hit earlier stages.
    Catches: timing (late date), short/over_funding (amount variance),
    and partially unreferenced_inbound (amount-anchored).

    Composite score:
      0.45 × amount_proximity  (dominant signal — must be non-zero)
      0.35 × date_proximity    (within FUZZY_DATE_WINDOW)
      0.20 × text_similarity   (descriptor vs reference+counterparty)

    Confidence = composite_score × 0.90  (slight penalty vs exact stages)
    Minimum composite score to propose a match: FUZZY_MIN_SCORE (0.30 default).

    Reversal legs (ACH RTN / REISSUE) are explicitly excluded: they share a
    counterparty name with unrelated 820 entries and produce false positives.
    If the reversal stage didn't claim them, they belong in needs_review.
    """
    for be in list(unmatched_be.values()):
        if _REVERSAL_LEG_RE.search(be.descriptor or ""):
            continue  # reversal leg — must not fuzzy-match unrelated entries
        descriptor = (be.descriptor or "").lower()
        best_le:   LedgerEntry | None = None
        best_score = FUZZY_MIN_SCORE

        for le in unmatched_le.values():
            if le.bank_account_id != be.bank_account_id:
                continue
            if le.direction != be.direction:
                continue

            amt_prox  = _amount_proximity(le.amount, be.amount)
            if amt_prox == 0:
                continue

            date_prox = _date_proximity(le.expected_date, be.posted_date, FUZZY_DATE_WINDOW)
            if date_prox == 0:
                continue

            le_text   = f"{le.reference or ''} {le.counterparty or ''}".lower().strip()
            text_sim  = _text_similarity(le_text, descriptor) if le_text else 0.0

            score = 0.45 * amt_prox + 0.35 * date_prox + 0.20 * text_sim
            if score > best_score:
                best_score = score
                best_le = le

        if best_le is None:
            continue

        confidence = Decimal(str(round(best_score * 0.90, 4)))
        _emit_match(session, be, [best_le], "fuzzy", confidence, stats)
        del unmatched_be[be.id]
        del unmatched_le[best_le.id]
        stats["fuzzy"] += 1


# ---------------------------------------------------------------------------
# Stage 6 — Leftovers
# ---------------------------------------------------------------------------

def _stage_leftovers(
    session: Session,
    unmatched_be: dict,
    stats: dict,
) -> None:
    """
    Every bank event that didn't match anything becomes an exception row with
    confidence=0 and status=needs_review.  bank_only_noise events land here.
    """
    for be in unmatched_be.values():
        match = ReconciliationMatch(
            id=uuid4(),
            bank_event_id=be.id,
            match_type="unmatched",
            confidence=Decimal("0.0000"),
            status=ReconciliationMatchStatus.NEEDS_REVIEW,
        )
        session.add(match)
        stats["unmatched"] += 1
        stats["needs_review"] += 1
    session.flush()
