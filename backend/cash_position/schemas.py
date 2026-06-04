"""
Pydantic schemas for the cash-position endpoint.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class GroupPosition(BaseModel):
    group_id: str
    group_name: str
    funded_balance: Decimal
    pending_claims_liability: Decimal
    available_to_cover: Decimal
    coverage_status: Literal["healthy", "watch", "shortfall"]
    member_count: int


class CashPositionSummary(BaseModel):
    total_funded: Decimal
    total_pending_liability: Decimal
    groups_in_shortfall: int


class CashPositionResponse(BaseModel):
    summary: CashPositionSummary
    groups: list[GroupPosition]


class ClearedEntry(BaseModel):
    id: str
    entry_type: str
    direction: str
    amount: Decimal
    expected_date: date
    reference: str | None
    counterparty: str | None
    status: str


class GroupPositionDetail(GroupPosition):
    cleared_entries: list[ClearedEntry]
    pending_entries: list[ClearedEntry]
