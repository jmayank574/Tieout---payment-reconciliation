"""
FastAPI routers for the exception resolution workflow.

/exceptions  — list, detail, stats, and all resolution actions
/audit       — audit history keyed on bank_event_id
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from typing import Annotated
from sqlalchemy.exc import SQLAlchemyError

from backend.db.connection import SessionLocal
from backend.exceptions import service
from backend.exceptions.schemas import (
    AcceptRequest,
    FlagRequest,
    MatchRequest,
    ReopenRequest,
    SplitRequest,
    WriteOffRequest,
)

exceptions_router = APIRouter(prefix="/exceptions", tags=["exceptions"])
audit_router = APIRouter(prefix="/audit", tags=["audit"])


def _session():
    return SessionLocal()


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@exceptions_router.get("/stats")
def get_stats():
    session = _session()
    try:
        return service.get_stats(session)
    finally:
        session.close()


@exceptions_router.get("")
def list_exceptions(
    status: Annotated[list[str] | None, Query()] = None,
    match_type: str | None = None,
    amount_min: Decimal | None = None,
    amount_max: Decimal | None = None,
    bank_account_id: UUID | None = None,
    sort: str = "confidence_asc",
    page: int = 1,
    page_size: int = 20,
):
    session = _session()
    try:
        return service.list_exceptions(
            session,
            statuses=status,
            match_type=match_type,
            amount_min=amount_min,
            amount_max=amount_max,
            bank_account_id=bank_account_id,
            sort=sort,
            page=page,
            page_size=page_size,
        )
    finally:
        session.close()


@exceptions_router.get("/{bank_event_id}")
def get_exception_detail(bank_event_id: UUID):
    session = _session()
    try:
        return service.get_exception_detail(session, bank_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Resolution action endpoints
# ---------------------------------------------------------------------------

@exceptions_router.post("/{bank_event_id}/accept")
def accept_exception(bank_event_id: UUID, body: AcceptRequest):
    session = _session()
    try:
        result = service.accept_exception(session, bank_event_id, body.actor, body.note)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


@exceptions_router.post("/{bank_event_id}/match")
def match_exception(bank_event_id: UUID, body: MatchRequest):
    session = _session()
    try:
        result = service.match_exception(
            session, bank_event_id, body.ledger_entry_ids, body.actor, body.note
        )
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


@exceptions_router.post("/{bank_event_id}/split")
def split_exception(bank_event_id: UUID, body: SplitRequest):
    session = _session()
    try:
        allocs = [
            {"ledger_entry_id": a.ledger_entry_id, "allocated_amount": a.allocated_amount}
            for a in body.allocations
        ]
        result = service.split_exception(session, bank_event_id, allocs, body.actor, body.note)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


@exceptions_router.post("/{bank_event_id}/write-off")
def write_off_exception(bank_event_id: UUID, body: WriteOffRequest):
    session = _session()
    try:
        result = service.write_off_exception(session, bank_event_id, body.reason, body.actor)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


@exceptions_router.post("/{bank_event_id}/flag")
def flag_exception(bank_event_id: UUID, body: FlagRequest):
    session = _session()
    try:
        result = service.flag_exception(session, bank_event_id, body.note, body.actor)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


@exceptions_router.post("/{bank_event_id}/reopen")
def reopen_exception(bank_event_id: UUID, body: ReopenRequest):
    session = _session()
    try:
        result = service.reopen_exception(session, bank_event_id, body.actor, body.note)
        session.commit()
        return result
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except SQLAlchemyError:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Audit endpoint
# ---------------------------------------------------------------------------

@audit_router.get("/{bank_event_id}")
def get_audit_history(bank_event_id: UUID):
    session = _session()
    try:
        return service.get_audit_history(session, bank_event_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    finally:
        session.close()
