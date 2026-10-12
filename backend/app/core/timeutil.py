"""UTC timestamp contract for the Velo API.

CONTRACT
--------
* Database columns are ``TIMESTAMP WITHOUT TIME ZONE`` and always hold **UTC**
  (naive values).  Use :func:`naive_utcnow` when writing them.
* Every timestamp that leaves the API is serialised as ISO-8601 UTC with an
  explicit ``Z`` suffix (``2026-10-11T10:15:30.123456Z``) via :data:`UTCDateTime`.
  A bare ``2026-10-11T10:15:30`` would be parsed as *local* time by Dart
  (``DateTime.parse``) and by JavaScript, silently shifting every ride
  duration by the device's UTC offset (+5h30m on an IST phone).
* Never compare a naive and an aware datetime; convert with :func:`as_utc`.
"""
from datetime import datetime, timezone
from typing import Annotated

from pydantic import BeforeValidator, PlainSerializer


def utcnow() -> datetime:
    """Timezone-aware current time in UTC."""
    return datetime.now(timezone.utc)


def naive_utcnow() -> datetime:
    """Naive UTC "now" — the representation stored in the DB columns."""
    return utcnow().replace(tzinfo=None)


def as_utc(value: datetime) -> datetime:
    """Return ``value`` as an aware UTC datetime.

    A naive value is interpreted as UTC (that is what the DB stores); an aware
    value is converted to UTC.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def to_naive_utc(value: datetime) -> datetime:
    """Normalise to the naive-UTC form used by DB columns."""
    return as_utc(value).replace(tzinfo=None)


def isoformat_utc(value: datetime) -> str:
    """ISO-8601 UTC string with an explicit ``Z`` suffix."""
    return as_utc(value).isoformat().replace("+00:00", "Z")


def _coerce_utc(value):
    # Pydantic validates ORM datetimes (naive) and parsed JSON; make both aware.
    if isinstance(value, datetime):
        return as_utc(value)
    return value


# Use in response schemas: validates naive->aware UTC, serialises with ``Z``.
UTCDateTime = Annotated[
    datetime,
    BeforeValidator(_coerce_utc),
    PlainSerializer(isoformat_utc, return_type=str, when_used="always"),
]
