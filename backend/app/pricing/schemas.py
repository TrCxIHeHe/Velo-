import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.core.money import Money
from app.core.timeutil import UTCDateTime


def _check_currency(v: str) -> str:
    v = v.strip().upper()
    if len(v) != 3 or not v.isalpha():
        raise ValueError("currency must be a 3-letter ISO 4217 code, e.g. INR")
    return v


class DockPairFareCreate(BaseModel):
    origin_dock_id: uuid.UUID
    destination_dock_id: uuid.UUID
    # Decimal in the request, 2dp max: a float like 12.3000000001 is rejected
    # rather than silently rounded.
    amount: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    currency: str = "INR"
    is_active: bool = True

    _currency = field_validator("currency")(_check_currency)


class DockPairFareUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    currency: str | None = None
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def _currency(cls, v):
        return None if v is None else _check_currency(v)


class DockPairFareResponse(BaseModel):
    id: uuid.UUID
    origin_dock_id: uuid.UUID
    destination_dock_id: uuid.UUID
    amount: Money
    currency: str
    is_active: bool
    created_at: UTCDateTime
    updated_at: UTCDateTime
    model_config = {"from_attributes": True}


class FareQuoteResponse(BaseModel):
    """Server-calculated estimate for ending ``ride_id`` at ``destination_dock_id``."""

    ride_id: uuid.UUID | None = None
    origin_dock_id: uuid.UUID
    destination_dock_id: uuid.UUID
    fare_amount: Money
    currency: str
    pricing_strategy: str
    pricing_reference_id: uuid.UUID | None = None
    wallet_balance: Money | None = None
    sufficient_balance: bool | None = None
