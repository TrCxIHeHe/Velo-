from app.core.exceptions import FareNotConfiguredError
from app.pricing.repository import DockPairFareRepository
from app.pricing.strategy import FareResult, PricingContext, PricingStrategy

STRATEGY_FIXED_DOCK_PAIR = "fixed_dock_pair"


class FixedDockPairStrategy(PricingStrategy):
    """Fare = the configured amount for the directed (origin -> destination) pair.

    Ride duration is recorded elsewhere but deliberately does not affect this
    fare. There is no fallback: a missing or inactive tariff is an error, never
    a guessed price.
    """

    name = STRATEGY_FIXED_DOCK_PAIR

    def __init__(self, fares: DockPairFareRepository) -> None:
        self.fares = fares

    async def calculate(self, ctx: PricingContext) -> FareResult:
        fare = await self.fares.find_by_pair(ctx.origin_dock_id, ctx.destination_dock_id)
        if fare is None or not fare.is_active:
            raise FareNotConfiguredError()
        return FareResult(
            amount=fare.amount,
            currency=fare.currency,
            strategy=self.name,
            reference_id=fare.id,
            details={
                "origin_dock_id": str(ctx.origin_dock_id),
                "destination_dock_id": str(ctx.destination_dock_id),
            },
        )
