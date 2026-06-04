"""
Pydantic v2 request schemas for the exception resolution workflow.

Only request bodies are modelled here — responses are returned as plain dicts
so FastAPI's jsonable_encoder handles type coercion consistently with the rest
of the codebase.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class AcceptRequest(BaseModel):
    actor: str = "operator"
    note: str | None = None


class MatchRequest(BaseModel):
    ledger_entry_ids: list[UUID]
    actor: str = "operator"
    note: str | None = None

    @field_validator("ledger_entry_ids")
    @classmethod
    def at_least_one(cls, v: list) -> list:
        if not v:
            raise ValueError("ledger_entry_ids must not be empty")
        return v


class AllocationItem(BaseModel):
    ledger_entry_id: UUID
    allocated_amount: Decimal

    @field_validator("allocated_amount")
    @classmethod
    def positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("allocated_amount must be positive")
        return v


class SplitRequest(BaseModel):
    allocations: list[AllocationItem]
    actor: str = "operator"
    note: str | None = None

    @field_validator("allocations")
    @classmethod
    def at_least_one(cls, v: list) -> list:
        if not v:
            raise ValueError("allocations must not be empty")
        return v


class WriteOffRequest(BaseModel):
    reason: str
    actor: str = "operator"


class FlagRequest(BaseModel):
    note: str
    actor: str = "operator"


class ReopenRequest(BaseModel):
    actor: str = "operator"
    note: str | None = None
