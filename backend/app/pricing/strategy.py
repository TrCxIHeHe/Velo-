"""Pricing strategy interface and value objects."""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class PricingContext:
    """Everything a strategy may need. Built by the server from stored records —
    never from client-supplied fare/origin values."""

    ride_id: uuid.UUID
    user_id: uuid.UUID
    origin_dock_id: uuid.UUID
    destination_dock_id: uuid.UUID
    started_at: datetime | None = None   # naive UTC, as stored
    ended_at: datetime | None = None     # None while quoting
    duration_seconds: int | None = None  # None while quoting


@dataclass(frozen=True)
class FareResult:
    amount: Decimal
    currency: str
    strategy: str                          # identifier of the strategy that produced it
    reference_id: uuid.UUID | None = None  # tariff record used (dock_pair_fares.id)
    details: dict = field(default_factory=dict)


class PricingStrategy(ABC):
    """Computes a fare. Implementations hold *no* ride-lifecycle logic."""

    #: Stable identifier persisted on the ride and returned in quotes.
    name: str

    @abstractmethod
    async def calculate(self, ctx: PricingContext) -> FareResult:
        """Return the fare for ``ctx`` or raise an ``AppException`` (for example
        ``FareNotConfiguredError``). Must not mutate any state."""
