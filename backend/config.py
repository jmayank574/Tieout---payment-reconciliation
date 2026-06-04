import os
from pathlib import Path
from decimal import Decimal
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

# Database
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://tieout_user:tieout_password@localhost:5433/tieout"
)

# Seed Generator Config
SEED = int(os.getenv("SEED", "42"))
NUM_GROUPS = int(os.getenv("NUM_GROUPS", "25"))
NUM_MEMBERS = int(os.getenv("NUM_MEMBERS", "8000"))
NUM_DAYS = int(os.getenv("NUM_DAYS", "90"))

# Minimum number of bank events guaranteed per non-clean, non-many_to_one exception type.
# many_to_one is structural (one per batch) so it never needs a floor.
EXCEPTION_FLOOR = int(os.getenv("EXCEPTION_FLOOR", "10"))

# Stop-loss constants
STOP_LOSS_PREMIUM_PEPM_MIN = Decimal("15.00")   # per member per month, minimum
STOP_LOSS_PREMIUM_PEPM_MAX = Decimal("60.00")   # per member per month, maximum
STOP_LOSS_REIMB_PROB = float(os.getenv("STOP_LOSS_REIMB_PROB", "0.15"))  # per group-month


# Exception mix — proportions are of BANK EVENTS, not ledger entries.
# many_to_one is generated structurally (one bank event per payment batch);
# its target here is for reporting / comparison only, not for random assignment.
# The remaining 7 types control the non-claim-payment exception pool.
EXCEPTION_MIX: Dict[str, float] = {
    "clean":                float(os.getenv("EXCEPTION_MIX_CLEAN",                "0.30")),
    "timing":               float(os.getenv("EXCEPTION_MIX_TIMING",               "0.05")),
    "many_to_one":          float(os.getenv("EXCEPTION_MIX_MANY_TO_ONE",          "0.40")),
    "one_to_many":          float(os.getenv("EXCEPTION_MIX_ONE_TO_MANY",          "0.05")),
    "reversal":             float(os.getenv("EXCEPTION_MIX_REVERSAL",             "0.05")),
    "short_over_funding":   float(os.getenv("EXCEPTION_MIX_SHORT_OVER_FUNDING",   "0.05")),
    "unreferenced_inbound": float(os.getenv("EXCEPTION_MIX_UNREFERENCED_INBOUND", "0.05")),
    "bank_only_noise":      float(os.getenv("EXCEPTION_MIX_BANK_ONLY_NOISE",      "0.05")),
}

total = sum(EXCEPTION_MIX.values())
if not (0.98 <= total <= 1.02):
    raise ValueError(
        f"Exception mix must sum to ~1.0, got {total}. Current mix: {EXCEPTION_MIX}"
    )

MIN_CLAIM_AMOUNT = Decimal("100.00")
MAX_CLAIM_AMOUNT = Decimal("5000.00")

# Directory where raw artifact files (835, 820, bank CSV) are written by seed
# and read by ingest.  Override with DATA_DIR env var if needed.
DATA_DIR: Path = Path(os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "data")))
