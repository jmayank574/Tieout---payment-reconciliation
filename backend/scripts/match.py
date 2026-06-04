"""make match — run the matching engine against the current DB state."""

import sys
import logging

sys.path.insert(0, ".")

from backend.db.connection import SessionLocal
from backend.match.engine import run_match

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    session = SessionLocal()
    try:
        log.info("Starting match engine …")
        stats = run_match(session)
        print("\nMatch run complete:")
        for k, v in stats.items():
            print(f"  {k:<20} {v}")
        print()
    except Exception:
        log.exception("Match engine failed")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
