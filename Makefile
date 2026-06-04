.PHONY: up down seed reset ingest summary match evaluate test resolve-demo help

PYTHON := .venv/Scripts/python
PYTEST := .venv/Scripts/pytest

help:
	@echo "Tieout - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  make up       - Start Postgres container"
	@echo "  make down     - Stop Postgres container"
	@echo "  make seed     - Drop & recreate DB, generate synthetic data, run ingest  [DESTRUCTIVE]"
	@echo "  make reset    - Alias for 'make seed'"
	@echo "  make ingest   - Re-run ingest pipeline only (no drop/recreate)"
	@echo "  make summary  - Print DB summary stats (counts, dollars, exceptions)"
	@echo "  make match    - Run matching engine (clears + rebuilds reconciliation_match)"
	@echo "  make evaluate - Print precision/recall scorecard vs ground_truth_link"
	@echo "  make test     - Run pytest suite"
	@echo "  make help     - Show this help"

up:
	docker-compose up -d
	@echo "Waiting for Postgres to be ready..."
	@sleep 5

down:
	docker-compose down

seed:
	@echo ""
	@echo "WARNING: This will DROP and RECREATE all tables and data."
	@echo "WARNING: All existing data will be DESTROYED."
	@echo ""
	PYTHONPATH=. $(PYTHON) backend/scripts/init_db.py

reset: seed

ingest:
	PYTHONPATH=. $(PYTHON) backend/scripts/ingest.py

summary:
	PYTHONPATH=. $(PYTHON) backend/scripts/summary.py

match:
	PYTHONPATH=. $(PYTHON) backend/scripts/match.py

evaluate:
	PYTHONPATH=. $(PYTHON) backend/scripts/evaluate.py

resolve-demo:
	PYTHONPATH=. $(PYTHON) -m backend.scripts.resolve_demo

test:
	PYTHONPATH=. $(PYTEST) tests/ -v
