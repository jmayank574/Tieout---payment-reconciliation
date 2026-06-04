"""Parser for 820 premium/funding artifact (fees, employer funding, stop-loss)."""

import json
import logging
from pathlib import Path

from pydantic import ValidationError

from backend.ingest.schemas import Raw820Row

log = logging.getLogger(__name__)


def parse_820(path: Path) -> list[Raw820Row]:
    """Parse 820_premium.json into validated row objects. Skips malformed rows."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    rows: list[Raw820Row] = []
    for i, tx in enumerate(data.get("transactions", [])):
        try:
            rows.append(Raw820Row(**tx))
        except (ValidationError, TypeError) as exc:
            log.warning("820 row %d skipped (row_ref=%s): %s", i, tx.get("row_ref", "?"), exc)
    return rows
