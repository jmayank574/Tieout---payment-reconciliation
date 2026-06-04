"""
Pydantic models for raw artifact rows parsed from 835, 820, and bank CSV files.
All ID fields (group_id, bank_account_id, etc.) are UUIDs coerced from strings.
Natural key fields (claim_id, row_ref, bank_reference) remain strings.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator


class Raw835Row(BaseModel):
    """One paid-claim remittance row from the 835 artifact."""
    claim_id: str          # natural key — stored as ledger_entry.reference
    group_id: UUID
    payment_batch_id: UUID
    provider_name: str
    paid_amount: Decimal
    paid_date: date
    bank_account_id: UUID

    @field_validator("paid_amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return Decimal(str(v))


class Raw820Row(BaseModel):
    """One financial transaction row from the 820 artifact (fees, funding, stop-loss)."""
    row_ref: str           # natural key — stored as ledger_entry.reference
    group_id: UUID
    entry_type: str
    direction: str
    amount: Decimal
    expected_date: date
    counterparty: str
    source_artifact: str
    bank_account_id: UUID

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return Decimal(str(v))


class RawBankRow(BaseModel):
    """One bank statement row from the bank CSV artifact."""
    bank_reference: str    # natural key — stored as bank_event.bank_reference
    bank_account_id: UUID
    posted_date: date
    amount: Decimal
    direction: str
    descriptor: str

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, v):
        return Decimal(str(v))
