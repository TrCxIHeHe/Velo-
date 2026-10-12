"""Fixed dock-pair strategy + the strategy abstraction itself."""
import uuid
from decimal import Decimal

import pytest

from app.core.exceptions import FareNotConfiguredError
from app.pricing.fixed_pair import STRATEGY_FIXED_DOCK_PAIR, FixedDockPairStrategy
from app.pricing.repository import DockPairFareRepository
from app.pricing.service import PricingService
from app.pricing.strategy import FareResult, PricingContext, PricingStrategy


def _ctx(origin, destination, **kw):
    return PricingContext(
        ride_id=uuid.uuid4(), user_id=uuid.uuid4(),
        origin_dock_id=origin, destination_dock_id=destination, **kw,
    )


async def test_fare_is_directional_and_independent(world, db_session):
    a = await world.dock("A")
    b = await world.dock("B")
    await world.fare(a, b, "20.00")
    await world.fare(b, a, "35.50")
    pricing = PricingService(DockPairFareRepository(db_session))

    ab = await pricing.calculate(_ctx(a, b))
    ba = await pricing.calculate(_ctx(b, a))

    assert ab.amount == Decimal("20.00") and ba.amount == Decimal("35.50")
    assert ab.currency == "INR" and ab.strategy == STRATEGY_FIXED_DOCK_PAIR
    assert ab.reference_id != ba.reference_id


async def test_duration_does_not_change_a_fixed_fare(world, db_session):
    a, b = await world.dock("A"), await world.dock("B")
    await world.fare(a, b, "20.00")
    pricing = PricingService(DockPairFareRepository(db_session))
    short = await pricing.calculate(_ctx(a, b, duration_seconds=5))
    long = await pricing.calculate(_ctx(a, b, duration_seconds=5 * 3600))
    assert short.amount == long.amount == Decimal("20.00")


async def test_missing_fare_raises_and_never_falls_back(world, db_session):
    a, b = await world.dock("A"), await world.dock("B")
    await world.fare(a, b, "20.00")  # only A->B; B->A is NOT configured
    pricing = PricingService(DockPairFareRepository(db_session))
    with pytest.raises(FareNotConfiguredError) as exc:
        await pricing.calculate(_ctx(b, a, duration_seconds=3600))
    assert exc.value.code == "FARE_NOT_CONFIGURED"


async def test_inactive_fare_is_treated_as_missing(world, db_session):
    a, b = await world.dock("A"), await world.dock("B")
    await world.fare(a, b, "20.00", active=False)
    with pytest.raises(FareNotConfiguredError):
        await PricingService(DockPairFareRepository(db_session)).calculate(_ctx(a, b))


async def test_unknown_strategy_name_is_a_configuration_error(db_session):
    with pytest.raises(RuntimeError, match="Unknown PRICING_STRATEGY"):
        _ = PricingService(DockPairFareRepository(db_session), strategy_name="nope").strategy


async def test_new_strategy_plugs_in_without_touching_ride_completion(world, db_session):
    """Extensibility proof: a time-based strategy is selected by name only.

    ``RideService`` is not modified or subclassed — it just asks PricingService.
    """
    class PerMinuteStrategy(PricingStrategy):
        name = "test_per_minute"

        async def calculate(self, ctx):
            minutes = max((ctx.duration_seconds or 0) // 60, 1)
            return FareResult(amount=Decimal("3.00") * minutes, currency="INR", strategy=self.name)

    a = await world.dock("A", vehicles=1)
    b = await world.dock("B")
    await world.fund(100)
    ride = await world.start_ride(a)

    svc = world.service()
    original = svc.pricing._build_strategies
    svc.pricing._strategy_name = "test_per_minute"
    svc.pricing._build_strategies = lambda: {**original(), "test_per_minute": PerMinuteStrategy()}

    ended = await svc.end_ride(world.user_id, ride.id, b)  # no fare row exists for A->B
    assert ended.fare_amount == 3.0
    assert ended.pricing_strategy == "test_per_minute"
    assert await world.balance() == pytest.approx(97.0)


def test_fixed_pair_is_a_pricing_strategy():
    assert issubclass(FixedDockPairStrategy, PricingStrategy)
