"""Money helpers.

Stored amounts for the tariff table are NUMERIC(10, 2) / ``Decimal``. On the
wire they are JSON numbers with at most two decimals (the same shape as the
legacy ``fare_amount``), so clients parse a single numeric format.
"""
from decimal import ROUND_HALF_UP, Decimal
from typing import Annotated

from pydantic import PlainSerializer

TWO_PLACES = Decimal("0.01")


def quantize_money(value: Decimal | float | int | str) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


Money = Annotated[Decimal, PlainSerializer(lambda d: float(d), return_type=float, when_used="json")]
