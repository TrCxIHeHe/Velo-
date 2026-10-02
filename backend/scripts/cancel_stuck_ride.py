"""
Cancel a PENDING/ACTIVE development ride for a user.

Default test user:
    +919876500000

This is a recovery utility. It:
  - finds the newest PENDING or ACTIVE ride
  - releases its vehicle, if one is attached
  - releases the vehicle's dock slot, if it is still assigned
  - clears vehicle.slot_id
  - marks the ride CANCELLED

Run from backend/:
    python scripts/cancel_stuck_ride.py
    python scripts/cancel_stuck_ride.py --phone +919876500000
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from app.database import AsyncSessionFactory
from app.models.dock import DockSlot
from app.models.ride import Ride
from app.models.user import User
from app.models.vehicle import Vehicle


DEFAULT_PHONE = "+919876500000"


async def cancel_stuck_ride(phone: str) -> None:
    async with AsyncSessionFactory() as session:
        user_result = await session.execute(
            select(User).where(User.phone_number == phone)
        )
        user = user_result.scalar_one_or_none()

        if user is None:
            raise RuntimeError(f"No user found with phone {phone}")

        ride_result = await session.execute(
            select(Ride)
            .where(
                Ride.user_id == user.id,
                Ride.status.in_(["PENDING", "ACTIVE"]),
            )
            .order_by(desc(Ride.created_at))
            .limit(1)
        )
        ride = ride_result.scalar_one_or_none()

        if ride is None:
            print("No PENDING or ACTIVE ride found.")
            return

        print(f"Found ride: {ride.id}")
        print(f"  Status:     {ride.status}")
        print(f"  Vehicle ID: {ride.vehicle_id}")

        if ride.vehicle_id is not None:
            vehicle = await session.get(Vehicle, ride.vehicle_id)

            if vehicle is not None:
                print(f"  Vehicle:    {vehicle.id}")
                print(f"  Slot ID:    {vehicle.slot_id}")

                # If the vehicle is still assigned to a dock slot, make
                # that slot available again.
                if vehicle.slot_id is not None:
                    slot = await session.get(DockSlot, vehicle.slot_id)
                    if slot is not None:
                        slot.is_occupied = False
                        print(f"  Released slot: {slot.id}")

                vehicle.slot_id = None
                vehicle.status = "AVAILABLE"
                print("  Vehicle status -> AVAILABLE")
                print("  Vehicle slot   -> None")

        ride.status = "CANCELLED"

        await session.commit()

        print(f"Ride {ride.id} -> CANCELLED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Cancel a stuck Velo ride")
    parser.add_argument("--phone", default=DEFAULT_PHONE)
    args = parser.parse_args()

    try:
        asyncio.run(cancel_stuck_ride(args.phone))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
