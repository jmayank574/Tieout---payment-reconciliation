"""
Initialize the database: drop tables, create schema, populate synthetic data,
then run the ingest pipeline to produce canonical ledger_entry and bank_event rows.
Run with: python backend/scripts/init_db.py  (or: make seed)
"""

import sys
from backend.db.connection import init_db, drop_db
from backend.seed.generator import generate_synthetic_data
from backend.ingest.pipeline import run_ingest
from backend.config import SEED


def main():
    print()
    print("=" * 70)
    print("WARNING: This script will DROP all tables and data!")
    print("=" * 70)
    print()

    try:
        print("[1/4] Dropping existing tables...")
        drop_db()
        print("      Done")

        print("[2/4] Creating schema...")
        init_db()
        print("      Done")

        print(f"[3/4] Generating synthetic data (seed={SEED})...")
        result = generate_synthetic_data(seed=SEED)
        print("      Done")
        print(f"        groups:             {len(result['groups'])}")
        print(f"        members:            {len(result['members'])}")
        print(f"        claims:             {len(result['claims'])}")
        print(f"        batches:            {len(result['batches'])}")
        print(f"        ground_truth_links: {len(result['ground_truth_links'])}")
        print(f"        835 records:        {len(result['records_835'])}")
        print(f"        820 records:        {len(result['records_820'])}")
        print(f"        bank records:       {len(result['bank_records'])}")

        print("[4/4] Running ingest pipeline...")
        stats = run_ingest()
        print("      Done")
        print(f"        ledger_entry (835): {stats['written_ledger_835']}")
        print(f"        ledger_entry (820): {stats['written_ledger_820']}")
        print(f"        bank_event:         {stats['written_bank_events']}")
        rt = stats["roundtrip"]
        print(f"        count match:        {rt['count_ok']}")
        print(f"        total match:        {rt['total_ok']}")

        print()
        print("=" * 70)
        print("Seeding complete!")
        print("=" * 70)
        return 0

    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
