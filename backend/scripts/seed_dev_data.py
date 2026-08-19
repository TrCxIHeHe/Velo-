"""
Seeds a complete development environment for testing:

    Login
      ↓
    GET /api/v1/docks
      ↓
    Select available dock
      ↓
    POST /api/v1/rides/token
      ↓
    QR generated
      ↓
    ESP32-CAM scans QR
      ↓
    POST /api/v1/docks/{dock_id}/scan

Usage from backend/ with venv active:

    alembic upgrade head
    python scripts/seed_dev_data.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionFactory
from app.models.dock import Dock, DockSlot
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import Wallet


# ============================================================
# FIXED DEVELOPMENT IDs
# ============================================================

DEV_USER_ID = uuid.UUID(
    "11111111-1111-1111-1111-111111111111"
)

DEV_VEHICLE_ID = uuid.UUID(
    "22222222-2222-2222-2222-222222222222"
)

DEV_DOCK_ID = uuid.UUID(
    "33333333-3333-3333-3333-333333333333"
)

DEV_SLOT_ID = uuid.UUID(
    "44444444-4444-4444-4444-444444444444"
)

DEV_WALLET_BALANCE = 1000.0


async def main():
    async with AsyncSessionFactory() as session:

        # ====================================================
        # 1. DEV USER
        # ====================================================

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
            # Keep the development account usable.
            user.firebase_uid = "debug-uid-1"
            user.phone_number = "+910000000001"
            user.name = "Debug User"
            user.role = "USER"
            user.is_active = True

            print(f"Dev user already exists: {DEV_USER_ID}")

        # ====================================================
        # 2. DEV WALLET
        # ====================================================

        from sqlalchemy import select

        wallet_result = await session.execute(
            select(Wallet).where(
                Wallet.user_id == DEV_USER_ID
            )
        )

        wallet = wallet_result.scalar_one_or_none()

        if wallet is None:
            wallet = Wallet(
                user_id=DEV_USER_ID,
                balance=DEV_WALLET_BALANCE,
                currency="INR",
            )

            session.add(wallet)

            print(
                f"Created dev wallet with balance: "
                f"₹{DEV_WALLET_BALANCE:.2f}"
            )

        else:
            # Reset the development wallet to a known balance
            # every time the seed script is run.
            wallet.balance = DEV_WALLET_BALANCE
            wallet.currency = "INR"

            print(
                f"Reset dev wallet balance to: "
                f"₹{DEV_WALLET_BALANCE:.2f}"
            )

        # ====================================================
        # 3. DEV DOCK
        # ====================================================

        dock = await session.get(Dock, DEV_DOCK_ID)

        if dock is None:
            dock = Dock(
                id=DEV_DOCK_ID,
                name="MG Road Dock",
                location_lat=12.9716,
                location_lng=77.5946,
                address="MG Road, Bengaluru",
                total_slots=1,
                is_active=True,
            )

            session.add(dock)

            print(f"Created dev dock: {DEV_DOCK_ID}")

        else:
            dock.name = "MG Road Dock"
            dock.location_lat = 12.9716
            dock.location_lng = 77.5946
            dock.address = "MG Road, Bengaluru"
            dock.total_slots = 1
            dock.is_active = True

            print(f"Reset dev dock: {DEV_DOCK_ID}")

        # ====================================================
        # 4. DEV DOCK SLOT
        # ====================================================

        slot = await session.get(DockSlot, DEV_SLOT_ID)

        if slot is None:
            slot = DockSlot(
                id=DEV_SLOT_ID,
                dock_id=DEV_DOCK_ID,
                slot_number=1,
                is_occupied=False,
            )

            session.add(slot)

            print(f"Created available dev slot: {DEV_SLOT_ID}")

        else:
            slot.dock_id = DEV_DOCK_ID
            slot.slot_number = 1
            slot.is_occupied = False

            print(f"Reset dev slot to AVAILABLE: {DEV_SLOT_ID}")

        # ====================================================
        # 5. DEV VEHICLE
        # ====================================================

        vehicle = await session.get(
            Vehicle,
            DEV_VEHICLE_ID,
        )

        if vehicle is None:
            vehicle = Vehicle(
                id=DEV_VEHICLE_ID,
                qr_code="DEV-QR-0001",
                status="AVAILABLE",
                battery_level=100,
                slot_id=DEV_SLOT_ID,
            )

            session.add(vehicle)

            print(f"Created available dev vehicle: {DEV_VEHICLE_ID}")

        else:
            vehicle.qr_code = "DEV-QR-0001"
            vehicle.status = "AVAILABLE"
            vehicle.battery_level = 100
            vehicle.slot_id = DEV_SLOT_ID

            print(f"Reset dev vehicle to AVAILABLE: {DEV_VEHICLE_ID}")

        # ====================================================
        # COMMIT
        # ====================================================

        await session.commit()

    print()
    print("=" * 60)
    print("DEVELOPMENT TEST DATA READY")
    print("=" * 60)

    print(f"User ID:       {DEV_USER_ID}")
    print(f"Wallet:        ₹{DEV_WALLET_BALANCE:.2f}")
    print(f"Dock ID:       {DEV_DOCK_ID}")
    print(f"Slot ID:       {DEV_SLOT_ID}")
    print(f"Vehicle ID:    {DEV_VEHICLE_ID}")
    print()
    print("Dock:          ACTIVE")
    print("Slot:          AVAILABLE")
    print("Vehicle:       AVAILABLE")
    print("Wallet:        ₹1000")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())