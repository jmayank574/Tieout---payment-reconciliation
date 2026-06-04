"""
Ingest API endpoints.

POST /ingest/run        — trigger a full ingest from data/raw/
GET  /ingest/runs       — list audit_log entries for past ingest runs
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from sqlalchemy import desc

from backend.config import DATA_DIR
from backend.db.connection import SessionLocal
from backend.db.models import AuditLog
from backend.ingest.pipeline import run_ingest

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/run")
def trigger_ingest():
    """Parse artifact files and write canonical ledger_entry / bank_event rows."""
    data_dir = Path(DATA_DIR) / "raw"
    if not data_dir.exists():
        raise HTTPException(status_code=404, detail=f"Artifact directory not found: {data_dir}")
    try:
        stats = run_ingest(data_dir)
        return {"status": "ok", "stats": stats}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/runs")
def list_ingest_runs(limit: int = 20):
    """Return the most recent ingest audit_log entries."""
    session = SessionLocal()
    try:
        rows = (
            session.query(AuditLog)
            .filter(AuditLog.action == "ingest_run")
            .order_by(desc(AuditLog.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(r.id),
                "actor": r.actor,
                "created_at": r.created_at.isoformat(),
                "payload": r.payload,
            }
            for r in rows
        ]
    finally:
        session.close()
