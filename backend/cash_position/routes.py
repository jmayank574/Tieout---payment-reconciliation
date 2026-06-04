"""
FastAPI router for cash-position endpoints.

GET /cash-position            — all groups, sorted worst coverage first
GET /cash-position/{group_id} — single group with contributing ledger entries
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from backend.db.connection import SessionLocal
from backend.cash_position import service

router = APIRouter(prefix="/cash-position", tags=["cash-position"])


def _session():
    return SessionLocal()


@router.get("")
def get_cash_positions():
    session = _session()
    try:
        return service.get_all_positions(session)
    finally:
        session.close()


@router.get("/{group_id}")
def get_group_cash_position(group_id: UUID):
    session = _session()
    try:
        detail = service.get_group_detail(session, group_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Group not found")
        return detail
    finally:
        session.close()
