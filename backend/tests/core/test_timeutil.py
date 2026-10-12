"""Timestamp contract: DB stores naive UTC; API emits ISO-8601 UTC with a ``Z``."""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.timeutil import as_utc, isoformat_utc, naive_utcnow, to_naive_utc, utcnow
from app.ride.schemas import RideResponse

IST = timezone(timedelta(hours=5, minutes=30))


def _ride_payload(**over):
    base = dict(
        id=uuid.uuid4(), user_id=uuid.uuid4(), vehicle_id=None, start_dock_id=uuid.uuid4(),
        end_dock_id=None, status="ACTIVE", started_at=None, ended_at=None,
        duration_seconds=None, fare_amount=None, fare_currency="INR",
        created_at=datetime(2026, 10, 11, 10, 0, 0),
    )
    base.update(over)
    return base


def test_naive_db_timestamp_is_serialised_as_utc_with_z():
    ride = RideResponse(**_ride_payload(started_at=datetime(2026, 10, 11, 10, 15, 30, 123456)))
    dumped = ride.model_dump(mode="json")
    assert dumped["started_at"] == "2026-10-11T10:15:30.123456Z"
    assert dumped["created_at"] == "2026-10-11T10:00:00Z"
    assert dumped["ended_at"] is None


def test_ist_aware_input_is_converted_to_utc():
    # 15:45:30 IST == 10:15:30 UTC
    ride = RideResponse(**_ride_payload(started_at=datetime(2026, 10, 11, 15, 45, 30, tzinfo=IST)))
    assert ride.model_dump(mode="json")["started_at"] == "2026-10-11T10:15:30Z"


def test_json_string_round_trip_keeps_the_same_instant():
    ride = RideResponse(**_ride_payload(started_at=datetime(2026, 10, 11, 10, 0, 0)))
    parsed = RideResponse.model_validate_json(ride.model_dump_json())
    assert as_utc(parsed.started_at) == as_utc(ride.started_at)


def test_helpers():
    assert utcnow().tzinfo is not None
    assert naive_utcnow().tzinfo is None
    assert as_utc(datetime(2026, 1, 1)).tzinfo == timezone.utc
    assert to_naive_utc(datetime(2026, 1, 1, 5, 30, tzinfo=IST)) == datetime(2026, 1, 1, 0, 0)
    assert isoformat_utc(datetime(2026, 1, 1, 5, 30, tzinfo=IST)) == "2026-01-01T00:00:00Z"


def test_duration_is_independent_of_the_server_or_device_zone():
    """Elapsed time is a difference of two UTC instants; an IST view of the same
    instants must give the identical duration."""
    start = datetime(2026, 10, 11, 10, 0, 0)            # naive UTC as stored
    end = start + timedelta(minutes=12, seconds=34)
    as_ist = lambda d: as_utc(d).astimezone(IST)
    assert (as_utc(end) - as_utc(start)).total_seconds() == 754
    assert (as_ist(end) - as_ist(start)).total_seconds() == 754
