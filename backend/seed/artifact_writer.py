"""
Writes generator output to raw artifact files consumed by the ingest pipeline.

835_remittance.json  — one row per paid claim (claim_payment ledger source)
820_premium.json     — employer funding, admin fees, stop-loss entries
bank_transactions.csv — bank statement rows
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


def write_artifacts(
    records_835: list[dict],
    records_820: list[dict],
    bank_records: list[dict],
    data_dir: Path,
) -> None:
    raw_dir = Path(data_dir) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    _write_835(records_835, raw_dir)
    _write_820(records_820, raw_dir)
    _write_bank(bank_records, raw_dir)


def _write_835(records: list[dict], raw_dir: Path) -> None:
    path = raw_dir / "835_remittance.json"
    payload = {
        "artifact_type": "835",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transaction_count": len(records),
        "transactions": records,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_820(records: list[dict], raw_dir: Path) -> None:
    path = raw_dir / "820_premium.json"
    payload = {
        "artifact_type": "820",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "transaction_count": len(records),
        "transactions": records,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_bank(records: list[dict], raw_dir: Path) -> None:
    path = raw_dir / "bank_transactions.csv"
    if not records:
        path.write_text("bank_reference,bank_account_id,posted_date,amount,direction,descriptor\n", encoding="utf-8")
        return
    fieldnames = ["bank_reference", "bank_account_id", "posted_date", "amount", "direction", "descriptor"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
