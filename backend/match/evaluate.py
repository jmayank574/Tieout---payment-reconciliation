"""
Evaluator: compare reconciliation_match output against ground_truth_link.

Metrics computed:
  - Precision  = |TP| / |predicted pairs|   (penalizes over-matching / false positives)
  - Recall     = |TP| / |ground truth pairs| (penalizes missed matches)
  - F1         = harmonic mean of precision and recall
  - False positives = |predicted pairs| - |TP|
  - Auto-match rate = auto-matched bank events / total bank events
  - Per-exception-type recall (8 types)
  - Confusion summary: unmatched ground-truth pairs grouped by exception type

A "predicted pair" is (bank_event_id, ledger_entry_id) drawn from
reconciliation_match + match_ledger_entry.  Unmatched rows (no ledger entries)
contribute no predicted pairs but do affect auto_match_rate.

A "ground truth pair" is (bank_event_id, ledger_entry_id) from ground_truth_link
where ledger_entry_id IS NOT NULL.  bank_only_noise rows (ledger_entry_id NULL)
are excluded from the pair set — the engine can only be evaluated on matchable pairs.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.db.models import (
    BankEvent,
    ExceptionType,
    GroundTruthLink,
    MatchLedgerEntry,
    ReconciliationMatch, ReconciliationMatchStatus,
)


def compute_scorecard(session: Session) -> dict:
    """
    Return a scorecard dict.  Does NOT print anything — callers decide format.
    """
    # ── Ground truth pairs (excludes bank_only_noise) ───────────────────
    gtl_rows = session.query(GroundTruthLink).all()
    gt_pairs: set[tuple] = {
        (str(gtl.bank_event_id), str(gtl.ledger_entry_id))
        for gtl in gtl_rows
        if gtl.ledger_entry_id is not None and gtl.bank_event_id is not None
    }

    # Map (bank_event_id, ledger_entry_id) → exception_type for per-type analysis
    gt_pair_type: dict[tuple, str] = {
        (str(gtl.bank_event_id), str(gtl.ledger_entry_id)): gtl.exception_type.value
        for gtl in gtl_rows
        if gtl.ledger_entry_id is not None and gtl.bank_event_id is not None
    }

    # ── Predicted pairs from engine output ──────────────────────────────
    # Exclude operator-resolved match types (manual, split) so Step 4 actions
    # do not pollute the engine's precision/recall scorecard.
    _ENGINE_MATCH_TYPES = ("exact", "many_to_one", "one_to_many", "reversal", "fuzzy")
    predicted_pairs: set[tuple] = set()
    match_rows = (
        session.query(ReconciliationMatch)
        .filter(ReconciliationMatch.match_type.in_(_ENGINE_MATCH_TYPES))
        .all()
    )
    match_ids = [m.id for m in match_rows]

    if match_ids:
        mle_rows = (
            session.query(MatchLedgerEntry)
            .filter(MatchLedgerEntry.reconciliation_match_id.in_(match_ids))
            .all()
        )
        # Build bank_event_id for each match
        match_id_to_be: dict = {str(m.id): str(m.bank_event_id) for m in match_rows}
        for mle in mle_rows:
            be_id = match_id_to_be.get(str(mle.reconciliation_match_id))
            if be_id:
                predicted_pairs.add((be_id, str(mle.ledger_entry_id)))

    # ── Core metrics ────────────────────────────────────────────────────
    tp_pairs  = predicted_pairs & gt_pairs
    tp        = len(tp_pairs)
    fp        = len(predicted_pairs) - tp
    fn        = len(gt_pairs) - tp

    precision = tp / len(predicted_pairs) if predicted_pairs else 0.0
    recall    = tp / len(gt_pairs)        if gt_pairs        else 0.0
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0 else 0.0
    )

    # ── Auto-match rate ─────────────────────────────────────────────────
    total_events = session.query(func.count(BankEvent.id)).scalar() or 0
    auto_matched = (
        session.query(func.count(ReconciliationMatch.id))
        .filter(ReconciliationMatch.status == ReconciliationMatchStatus.MATCHED)
        .scalar() or 0
    )
    auto_match_rate = auto_matched / total_events if total_events else 0.0

    # ── Per-exception-type recall ────────────────────────────────────────
    # For noise, there are no predicted pairs so recall is not meaningful
    per_type: dict[str, dict] = {}
    for exc in ExceptionType:
        if exc == ExceptionType.BANK_ONLY_NOISE:
            # Noise: count how many noise events ended up unmatched (correct behavior)
            noise_be_ids = {
                str(gtl.bank_event_id)
                for gtl in gtl_rows
                if gtl.exception_type == ExceptionType.BANK_ONLY_NOISE
                and gtl.bank_event_id is not None
            }
            # A noise event is "correctly handled" if it has no predicted pairs
            predicted_noise_be = {be_id for (be_id, _) in predicted_pairs}
            correctly_unmatched = len(noise_be_ids - predicted_noise_be)
            per_type[exc.value] = {
                "total_events":        len(noise_be_ids),
                "correctly_unmatched": correctly_unmatched,
                "incorrectly_matched": len(noise_be_ids & predicted_noise_be),
                "recall":              None,  # not applicable
            }
            continue

        type_gt = {pair for pair, t in gt_pair_type.items() if t == exc.value}
        type_tp = predicted_pairs & type_gt
        per_type[exc.value] = {
            "total_gt_pairs": len(type_gt),
            "matched":        len(type_tp),
            "recall":         len(type_tp) / len(type_gt) if type_gt else None,
        }

    # ── Confusion: missed ground-truth pairs by exception type ───────────
    missed = gt_pairs - tp_pairs
    missed_by_type: dict[str, int] = defaultdict(int)
    for pair in missed:
        t = gt_pair_type.get(pair, "unknown")
        missed_by_type[t] += 1

    # ── False-positive examples (first 10) ──────────────────────────────
    fp_pairs = list(predicted_pairs - gt_pairs)[:10]

    return {
        "total_gt_pairs":   len(gt_pairs),
        "total_predicted":  len(predicted_pairs),
        "true_positives":   tp,
        "false_positives":  fp,
        "false_negatives":  fn,
        "precision":        round(precision, 4),
        "recall":           round(recall, 4),
        "f1":               round(f1, 4),
        "total_events":     total_events,
        "auto_matched":     auto_matched,
        "auto_match_rate":  round(auto_match_rate, 4),
        "per_type":         per_type,
        "missed_by_type":   dict(missed_by_type),
        "fp_examples":      fp_pairs,
    }


def print_scorecard(scorecard: dict) -> None:
    """Print a human-readable evaluation report to stdout."""
    s = scorecard
    print()
    print("=" * 60)
    print("  TIEOUT MATCHING ENGINE — EVALUATION SCORECARD")
    print("=" * 60)
    print(f"  Ground-truth pairs   : {s['total_gt_pairs']:>6}")
    print(f"  Predicted pairs      : {s['total_predicted']:>6}")
    print(f"  True positives       : {s['true_positives']:>6}")
    print(f"  False positives (FP) : {s['false_positives']:>6}")
    print(f"  False negatives (FN) : {s['false_negatives']:>6}")
    print("-" * 60)
    print(f"  Precision            : {s['precision']:>6.1%}")
    print(f"  Recall               : {s['recall']:>6.1%}")
    print(f"  F1 score             : {s['f1']:>6.1%}")
    print("-" * 60)
    print(f"  Total bank events    : {s['total_events']:>6}")
    print(f"  Auto-matched         : {s['auto_matched']:>6}  ({s['auto_match_rate']:.1%})")
    print(f"  Needs review         : {s['total_events'] - s['auto_matched']:>6}")
    print("=" * 60)
    print("  PER-EXCEPTION-TYPE RECALL")
    print("-" * 60)
    for exc_type, info in s["per_type"].items():
        if exc_type == "bank_only_noise":
            total   = info["total_events"]
            correct = info["correctly_unmatched"]
            wrong   = info["incorrectly_matched"]
            print(f"  {exc_type:<30} {total:>5} events  correctly_unmatched={correct}  wrongly_matched={wrong}")
        else:
            total   = info["total_gt_pairs"]
            matched = info["matched"]
            recall  = info["recall"]
            recall_s = f"{recall:.1%}" if recall is not None else "  n/a"
            print(f"  {exc_type:<30} {total:>5} pairs   matched={matched:<5}  recall={recall_s}")
    print("=" * 60)
    print("  MISSED GT PAIRS BY EXCEPTION TYPE")
    print("-" * 60)
    if s["missed_by_type"]:
        for exc_type, cnt in sorted(s["missed_by_type"].items(), key=lambda x: -x[1]):
            print(f"  {exc_type:<30} {cnt:>5} missed")
    else:
        print("  (none — perfect recall)")
    if s["false_positives"] > 0:
        print("=" * 60)
        print(f"  FALSE-POSITIVE PAIR EXAMPLES (first {len(s['fp_examples'])})")
        print("-" * 60)
        for be_id, le_id in s["fp_examples"]:
            print(f"  bank_event={be_id[:8]}…  ledger_entry={le_id[:8]}…")
    print("=" * 60)
    print()
