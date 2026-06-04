"""Parser for bank transactions CSV artifact."""

import csv
import logging
from pathlib import Path

from pydantic import ValidationError

from backend.ingest.schemas import RawBankRow

log = logging.getLogger(__name__)


def parse_bank(path: Path) -> list[RawBankRow]:
    """Parse bank_transactions.csv into validated row objects. Skips malformed rows."""
    rows: list[RawBankRow] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            try:
                rows.append(RawBankRow(**row))
            except (ValidationError, TypeError) as exc:
                log.warning("bank row %d skipped (bank_reference=%s): %s",
                            i, row.get("bank_reference", "?"), exc)
    return rows
