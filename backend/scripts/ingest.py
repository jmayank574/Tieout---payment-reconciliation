"""
Run the ingest pipeline: parse artifact files, write canonical rows, finalize ground truth.
Run with: python backend/scripts/ingest.py
Or: make ingest
"""

import sys
from backend.ingest.pipeline import run_ingest


def main():
    print()
    print("=" * 70)
    print("Tieout Ingest Pipeline")
    print("=" * 70)
    print()
    try:
        stats = run_ingest()

        print(f"  Parsed 835 rows:         {stats['parsed_835']}")
        print(f"  Parsed 820 rows:         {stats['parsed_820']}")
        print(f"  Parsed bank rows:        {stats['parsed_bank']}")
        print()
        print(f"  Written claim_payment:   {stats['written_ledger_835']}")
        print(f"  Written 820 entries:     {stats['written_ledger_820']}")
        print(f"  Written bank events:     {stats['written_bank_events']}")
        print()
        rt = stats["roundtrip"]
        print("  Round-trip check:")
        print(f"    Paid claims:           {rt['paid_claims']}")
        print(f"    Ingested payments:     {rt['ingested_claim_payments']}")
        print(f"    Count match:           {rt['count_ok']}")
        print(f"    Total match:           {rt['total_ok']}")
        print(f"    Batch/LE match:        {rt['batch_le_ok']}")
        print()
        print("=" * 70)
        print("Ingest complete!")
        print("=" * 70)
        return 0

    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
