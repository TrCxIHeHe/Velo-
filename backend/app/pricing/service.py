"""PricingService — the single entry point the ride lifecycle uses for fares.

Quotes and final fares go through the *same* ``calculate`` call, so an estimate
can never be computed by a different rule than the charge.
"""
import uuid

from app.audit.repository import AuditLogRepository
from app.config import settings
from app.core.exceptions import (
    DockNotFoundError, DockPairFareAlreadyExistsError, DockPairFareNotFoundError,
    InvalidFarePairError,
)
from app.dock.repository import DockRepository
from app.pricing.fixed_pair import STRATEGY_FIXED_DOCK_PAIR, FixedDockPairStrategy
from app.pricing.repository import DockPairFareRepository
from app.pricing.schemas import DockPairFareCreate, DockPairFareResponse, DockPairFareUpdate
from app.pricing.strategy import FareResult, PricingContext, PricingStrategy


class PricingService:
    def __init__(
        self,
        fare_repo: DockPairFareRepository,
        dock_repo: DockRepository | None = None,
        audit_repo: AuditLogRepository | None = None,
        strategy_name: str | None = None,
    ) -> None:
        self.fare_repo = fare_repo
        self.dock_repo = dock_repo
        self.audit_repo = audit_repo
        self._strategy_name = strategy_name or settings.PRICING_STRATEGY

    # ── strategy registry ────────────────────────────────────────────────
    def _build_strategies(self) -> dict[str, PricingStrategy]:
        """Add future strategies here (distance, time, subscription, promo, surge)."""
        return {STRATEGY_FIXED_DOCK_PAIR: FixedDockPairStrategy(self.fare_repo)}

    @property
    def strategy(self) -> PricingStrategy:
        strategies = self._build_strategies()
        try:
            return strategies[self._strategy_name]
        except KeyError:
            raise RuntimeError(
                f"Unknown PRICING_STRATEGY {self._strategy_name!r}; "
                f"available: {sorted(strategies)}"
            ) from None

    async def calculate(self, ctx: PricingContext) -> FareResult:
        """Quote (ctx without end data) or final fare (ctx with end data)."""
        return await self.strategy.calculate(ctx)

    # ── tariff administration (fixed dock-pair data) ─────────────────────
    async def create_fare(self, data: DockPairFareCreate, actor_id: uuid.UUID | None) -> DockPairFareResponse:
        await self._validate_pair(data.origin_dock_id, data.destination_dock_id)
        if await self.fare_repo.find_by_pair(data.origin_dock_id, data.destination_dock_id):
            raise DockPairFareAlreadyExistsError()
        fare = await self.fare_repo.create(
            data.origin_dock_id, data.destination_dock_id, data.amount, data.currency, data.is_active
        )
        await self._audit(
            actor_id, "DOCK_FARE_CREATED", fare.id,
            f"{fare.origin_dock_id}->{fare.destination_dock_id} amount={fare.amount} {fare.currency}",
        )
        return DockPairFareResponse.model_validate(fare)

    async def update_fare(
        self, fare_id: uuid.UUID, data: DockPairFareUpdate, actor_id: uuid.UUID | None
    ) -> DockPairFareResponse:
        fare = await self.fare_repo.find_by_id(fare_id)
        if fare is None:
            raise DockPairFareNotFoundError()
        changes = data.model_dump(exclude_none=True)
        before = f"amount={fare.amount} {fare.currency} active={fare.is_active}"
        if changes:
            fare = await self.fare_repo.update(fare_id, **changes)
        await self._audit(
            actor_id, "DOCK_FARE_UPDATED", fare.id,
            f"{before} -> amount={fare.amount} {fare.currency} active={fare.is_active}",
        )
        return DockPairFareResponse.model_validate(fare)

    async def get_fare(self, fare_id: uuid.UUID) -> DockPairFareResponse:
        fare = await self.fare_repo.find_by_id(fare_id)
        if fare is None:
            raise DockPairFareNotFoundError()
        return DockPairFareResponse.model_validate(fare)

    async def list_fares(self, **filters) -> list[DockPairFareResponse]:
        return [DockPairFareResponse.model_validate(f) for f in await self.fare_repo.list(**filters)]

    async def _validate_pair(self, origin: uuid.UUID, destination: uuid.UUID) -> None:
        if origin == destination:
            raise InvalidFarePairError()
        if self.dock_repo is not None:
            for dock_id in (origin, destination):
                if await self.dock_repo.find_by_id(dock_id) is None:
                    raise DockNotFoundError(f"Dock {dock_id} does not exist.")

    async def _audit(self, actor_id, action: str, fare_id: uuid.UUID, meta: str) -> None:
        if self.audit_repo is not None:
            await self.audit_repo.log(actor_id, action, "dock_pair_fare", str(fare_id), meta)



