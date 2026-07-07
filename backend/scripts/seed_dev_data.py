"""Seeds the minimum rows Track B needs to manually test wallet + dock
endpoints against a real PostgreSQL database.

WHY THIS SCRIPT EXISTS (READ BEFORE YOU SKIP IT)
--------------------------------------------------
Two foreign keys will bite you the first time you test against real
Postgres, and neither shows up in the SQLite-based pytest suite because
SQLite does not enforce foreign keys by default (see tests/conftest.py's
docstring for the full explanation):

  1. `wallets.user_id`      -> `users.id`
  2. `dock_slots.vehicle_id` -> `vehicles.id`

If you call POST /api/v1/wallet/credit with a random X-Debug-User-Id that
has no matching row in `users`, Postgres rejects the INSERT with a
ForeignKeyViolationError, which surfaces to you as a bare 500 Internal
Server Error (not one of our clean {"success": false, ...} envelopes,
because it's the database itself rejecting the write before our code
gets a chance to catch it).

Same story for POST /api/v1/docks/{id}/assign with a vehicle_id that
doesn't exist in `vehicles` — that table is owned by Track A's Vehicle
Service in the long run, but Track B's dock_slots table has a hard FK
against it, so for standalone manual testing you need at least one real
vehicle row to assign.

This script creates exactly one of each, with fixed, well-known UUIDs so
you can hardcode them in curl commands / Postman collections without
looking them up every time.

Usage (from backend/, venv active, after `alembic upgrade head`):
    python scripts/seed_dev_data.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionFactory  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.vehicle import Vehicle  # noqa: E402

DEV_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DEV_VEHICLE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


async def main():
    async with AsyncSessionFactory() as session:
        user = await session.get(User, DEV_USER_ID)
        if user is None:
            user = User(
                id=DEV_USER_ID,
                firebase_uid="debug-uid-1",
                phone_number="+910000000001",
                name="Debug User",
                role="USER",
                is_active=True,
            )
            session.add(user)
            print(f"Created dev user: {DEV_USER_ID}")
        else:
            print(f"Dev user already exists: {DEV_USER_ID}")

        vehicle = await session.get(Vehicle, DEV_VEHICLE_ID)
        if vehicle is None:
            vehicle = Vehicle(
                id=DEV_VEHICLE_ID,
                qr_code="DEV-QR-0001",
                status="AVAILABLE",
                battery_pct=100,
            )
            session.add(vehicle)
            print(f"Created dev vehicle: {DEV_VEHICLE_ID}")
        else:
            print(f"Dev vehicle already exists: {DEV_VEHICLE_ID}")

        await session.commit()

    print()
    print("Use these headers/values in curl or Postman:")
    print(f"  X-Debug-User-Id: {DEV_USER_ID}")
    print(f"  vehicle_id (for /docks/{{id}}/assign): {DEV_VEHICLE_ID}")


if __name__ == "__main__":
    asyncio.run(main())
