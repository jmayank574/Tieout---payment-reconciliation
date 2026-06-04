"""Parser for 835 remittance artifact (claim payments)."""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from backend.ingest.schemas import Raw835Row

log = logging.getLogger(__name__)


def parse_835(path: Path) -> list[Raw835Row]:
    """Parse 835_remittance.json into validated row objects. Skips malformed rows."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows: list[Raw835Row] = []
    for i, tx in enumerate(data.get("transactions", [])):
        try:
            rows.append(Raw835Row(**tx))
        except (ValidationError, TypeError) as exc:
            log.warning("835 row %d skipped (claim_id=%s): %s", i, tx.get("claim_id", "?"), exc)
    return rows
