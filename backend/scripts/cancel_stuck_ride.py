"""
Ad-hoc dev utility: cancel a user's stuck PENDING/ACTIVE ride and release
any vehicle/slot it holds, so they can request a new ride token.

Usage from backend/ with venv active:

    python scripts/cancel_stuck_ride.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.ride import Ride
from app.models.user import User
from app.models.vehicle import Vehicle

PHONE = "+919876500000"


async def main():
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.phone_number == PHONE))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with phone {PHONE}")
            return

        rresult = await session.execute(
            select(Ride).where(Ride.user_id == user.id, Ride.status.in_(["PENDING", "ACTIVE"]))
        )
        ride = rresult.scalar_one_or_none()
        if ride is None:
            print("No stuck ride found for this user.")
            return

        print(f"Found ride {ride.id} status={ride.status} vehicle_id={ride.vehicle_id}")

        if ride.vehicle_id:
            vehicle = await session.get(Vehicle, ride.vehicle_id)
            if vehicle is not None:
                vehicle.status = "AVAILABLE"
                print(f"Released vehicle {vehicle.id} back to AVAILABLE")

        ride.status = "CANCELLED"
        print(f"Cancelled ride {ride.id}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
