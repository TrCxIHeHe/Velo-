"""Timestamps over the real HTTP API are explicit UTC (``Z``), never naive."""
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.core.timeutil import naive_utcnow
from app.models import Ride

ISO_Z = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


async def test_active_ride_timestamps_have_an_explicit_utc_zone(client, world, db_session):
    a = await world.dock("A", vehicles=1)
    await world.fund(100)
    ride = await world.start_ride(a)
    # started 90 s ago, stored the way the DB stores it: naive UTC
    await db_session.execute(
        update(Ride).where(Ride.id == ride.id).values(started_at=naive_utcnow() - timedelta(seconds=90))
    )
    await db_session.commit()

    data = (await client.get("/api/v1/rides/active", headers=world.headers)).json()["data"]
    for key in ("started_at", "created_at"):
        assert ISO_Z.match(data[key]), data[key]

    started = datetime.fromisoformat(data["started_at"].replace("Z", "+00:00"))
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    assert 89 <= elapsed <= 95          # the elapsed time a client computes is correct


async def test_other_api_timestamps_follow_the_same_contract(client, world):
    await world.dock("A")
    docks = (await client.get("/api/v1/docks")).json()["data"]
    assert ISO_Z.match(docks[0]["created_at"])
