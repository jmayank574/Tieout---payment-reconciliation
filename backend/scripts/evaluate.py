"""make evaluate — print the scorecard comparing engine output to ground truth."""

import sys
import logging

sys.path.insert(0, ".")

from backend.db.connection import SessionLocal
from backend.match.evaluate import compute_scorecard, print_scorecard

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)


def main():
    session = SessionLocal()
    try:
        scorecard = compute_scorecard(session)
        print_scorecard(scorecard)
    except Exception:
        log.exception("Evaluate failed")
        sys.exit(1)
    finally:
        session.close()


if __name__ == "__main__":
    main()
