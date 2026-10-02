"""
Seed/reset the Velo physical-demo environment.

Target Firebase test user:
    +919876500000

Demo state after this script:

    Test user
      └── Wallet: ₹1000 + initial CREDIT transaction

    MG Road Dock
      ├── Slot 1 -> DEV scooter (AVAILABLE, 100% battery)
      └── Slot 2 -> EMPTY

    Koramangala Dock
      ├── Slot 1 -> EMPTY
      └── Slot 2 -> EMPTY

The first dock is the starting dock. The second dock is deliberately left
with a free slot so the complete ride lifecycle can be demonstrated:

    request token -> ESP32-CAM scan -> ride ACTIVE -> end ride at Dock B
    -> scooter parked in a free destination slot -> fare charged.

IMPORTANT — Firebase UID:
    The current backend creates/finds users by Firebase UID, not phone number.
    Therefore this script:
      1. finds the existing PostgreSQL user by +919876500000 if present, or
      2. creates it only when --firebase-uid is supplied.

If the user has already logged in through Firebase once, the normal workflow is:

    alembic upgrade head
    python scripts/seed_dev_data.py

If the PostgreSQL user does not exist yet:

    python scripts/seed_dev_data.py --firebase-uid YOUR_FIREBASE_UID

Usage from backend/:

    alembic upgrade head
    python scripts/seed_dev_data.py

Optional:

    python scripts/seed_dev_data.py --firebase-uid YOUR_FIREBASE_UID
    python scripts/seed_dev_data.py --balance 1000
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.database import AsyncSessionFactory
from app.models.dock import Dock, DockSlot
from app.models.ride import Ride
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import Wallet, WalletTransaction


# ---------------------------------------------------------------------------
# Fixed deterministic IDs for the physical demo.
# ---------------------------------------------------------------------------

DEV_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")

START_DOCK_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
START_SLOT_1_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")
START_SLOT_2_ID = uuid.UUID("44444444-4444-4444-4444-444444444445")

DEST_DOCK_ID = uuid.UUID("55555555-5555-5555-5555-555555555555")
DEST_SLOT_1_ID = uuid.UUID("66666666-6666-6666-6666-666666666666")
DEST_SLOT_2_ID = uuid.UUID("66666666-6666-6666-6666-666666666667")

DEV_VEHICLE_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

TEST_PHONE = "+919876500000"
TEST_USER_NAME = "Velo Test User"
DEV_WALLET_BALANCE = 1000.0

DEV_QR_CODE = "DEV-QR-0001"
SEED_TRANSACTION_REFERENCE = "seed:velo-demo-initial-balance"


async def get_or_create_test_user(session, firebase_uid: str | None) -> User:
    """
    Prefer the existing Firebase-linked user.

    This matters because the current AuthService looks users up by
    firebase_uid, while phone_number is unique in PostgreSQL.
    """

    # First try the known phone number. This allows the real Firebase-created
    # user to be reused without overwriting its real Firebase UID.
    result = await session.execute(
        select(User).where(User.phone_number == TEST_PHONE)
    )
    user = result.scalar_one_or_none()

    if user is not None:
        # The real Firebase test user is existing data. Never modify its
        # identity fields (Firebase UID, name, role, active state, etc.).
        # The seed owns only the demo data around this user.
        print(f"Using existing test user unchanged: {user.id}")
        print(f"  Phone:        {user.phone_number}")
        print(f"  Firebase UID: {user.firebase_uid}")
        print("  User record:  PRESERVED")
        return user

    if not firebase_uid:
        raise RuntimeError(
            "No PostgreSQL user exists for +919876500000.\n"
            "The current backend requires the real Firebase UID when creating "
            "the user.\n\n"
            "Either log in once with the Firebase test phone and run this "
            "script again, or run:\n\n"
            "  python scripts/seed_dev_data.py "
            "--firebase-uid YOUR_FIREBASE_UID"
        )

    # Use the historical deterministic UUID only when creating the user.
    existing_id = await session.get(User, DEV_USER_ID)
    if existing_id is not None:
        raise RuntimeError(
            f"Fixed demo user ID {DEV_USER_ID} already belongs to another "
            "user. Refusing to overwrite it."
        )

    user = User(
        id=DEV_USER_ID,
        firebase_uid=firebase_uid,
        phone_number=TEST_PHONE,
        name=TEST_USER_NAME,
        role="USER",
        is_active=True,
    )
    session.add(user)
    await session.flush()

    print(f"Created test user: {user.id}")
    print(f"  Phone:        {TEST_PHONE}")
    print(f"  Firebase UID: {firebase_uid}")

    return user


async def reset_wallet(session, user_id: uuid.UUID, balance: float) -> Wallet:
    result = await session.execute(
        select(Wallet).where(Wallet.user_id == user_id)
    )
    wallet = result.scalar_one_or_none()

    if wallet is None:
        wallet = Wallet(
            user_id=user_id,
            balance=balance,
            currency="INR",
        )
        session.add(wallet)
        await session.flush()
        print(f"Created wallet: {wallet.id}")
    else:
        wallet.balance = balance
        wallet.currency = "INR"
        print(f"Reset wallet: {wallet.id}")

    # The seed is a reset operation, so remove old demo ledger entries.
    await session.execute(
        delete(WalletTransaction).where(
            WalletTransaction.wallet_id == wallet.id
        )
    )

    transaction = WalletTransaction(
        wallet_id=wallet.id,
        type="CREDIT",
        source="TOPUP",
        amount=balance,
        balance_after=balance,
        reference_id=SEED_TRANSACTION_REFERENCE,
        note="Initial balance for Velo physical development demo",
    )
    session.add(transaction)

    await session.flush()

    print(f"  Balance: ₹{balance:.2f}")
    print(f"  Ledger:  +₹{balance:.2f} CREDIT")

    return wallet


async def reset_dock(
    session,
    dock_id: uuid.UUID,
    name: str,
    lat: float,
    lng: float,
    address: str,
    slot_ids: list[uuid.UUID],
) -> Dock:
    dock = await session.get(Dock, dock_id)

    if dock is None:
        dock = Dock(
            id=dock_id,
            name=name,
            location_lat=lat,
            location_lng=lng,
            address=address,
            total_slots=len(slot_ids),
            is_active=True,
        )
        session.add(dock)
        await session.flush()
        print(f"Created dock: {name} ({dock_id})")
    else:
        dock.name = name
        dock.location_lat = lat
        dock.location_lng = lng
        dock.address = address
        dock.total_slots = len(slot_ids)
        dock.is_active = True
        print(f"Reset dock: {name} ({dock_id})")

    for number, slot_id in enumerate(slot_ids, start=1):
        slot = await session.get(DockSlot, slot_id)

        if slot is None:
            slot = DockSlot(
                id=slot_id,
                dock_id=dock_id,
                slot_number=number,
                is_occupied=False,
            )
            session.add(slot)
        else:
            slot.dock_id = dock_id
            slot.slot_number = number
            slot.is_occupied = False

    await session.flush()
    return dock


async def reset_demo_ride_state(session, user_id: uuid.UUID) -> None:
    """
    A previous physical demo can leave a PENDING/ACTIVE ride behind.

    Do not delete ride history. Cancel only unfinished rides belonging to the
    test user so a fresh demo can request a new token.
    """

    result = await session.execute(
        select(Ride).where(
            Ride.user_id == user_id,
            Ride.status.in_(["PENDING", "ACTIVE"]),
        )
    )
    rides = result.scalars().all()

    for ride in rides:
        ride.status = "CANCELLED"
        print(f"Cancelled unfinished demo ride: {ride.id}")


async def reset_demo_vehicle(session) -> Vehicle:
    vehicle = await session.get(Vehicle, DEV_VEHICLE_ID)

    if vehicle is None:
        vehicle = Vehicle(
            id=DEV_VEHICLE_ID,
            qr_code=DEV_QR_CODE,
            vehicle_type="SCOOTER",
            battery_level=100,
            status="AVAILABLE",
            slot_id=START_SLOT_1_ID,
        )
        session.add(vehicle)
        print(f"Created demo scooter: {DEV_VEHICLE_ID}")
    else:
        vehicle.qr_code = DEV_QR_CODE
        vehicle.vehicle_type = "SCOOTER"
        vehicle.battery_level = 100
        vehicle.status = "AVAILABLE"
        vehicle.slot_id = START_SLOT_1_ID
        print(f"Reset demo scooter: {DEV_VEHICLE_ID}")

    await session.flush()
    return vehicle


async def main(firebase_uid: str | None, balance: float) -> None:
    if balance <= 0:
        raise ValueError("--balance must be greater than 0")

    async with AsyncSessionFactory() as session:
        # 1. Real Firebase test user / PostgreSQL user.
        user = await get_or_create_test_user(session, firebase_uid)

        # 2. Clean unfinished rides so the next token request is allowed.
        await reset_demo_ride_state(session, user.id)

        # 3. Wallet + matching ledger entry.
        await reset_wallet(session, user.id, balance)

        # 4. Starting dock: scooter lives here.
        await reset_dock(
            session,
            START_DOCK_ID,
            "MG Road Dock",
            12.9716,
            77.5946,
            "MG Road, Bengaluru",
            [START_SLOT_1_ID, START_SLOT_2_ID],
        )

        # 5. Destination dock: keep free slots available for ride ending.
        await reset_dock(
            session,
            DEST_DOCK_ID,
            "Koramangala Dock",
            12.9352,
            77.6245,
            "Koramangala, Bengaluru",
            [DEST_SLOT_1_ID, DEST_SLOT_2_ID],
        )

        # 6. Demo scooter starts in Start Dock / Slot 1.
        vehicle = await reset_demo_vehicle(session)

        # The scooter occupies its physical dock slot.
        start_slot = await session.get(DockSlot, START_SLOT_1_ID)
        start_slot.is_occupied = True

        # Keep all other demo slots free.
        for slot_id in [START_SLOT_2_ID, DEST_SLOT_1_ID, DEST_SLOT_2_ID]:
            slot = await session.get(DockSlot, slot_id)
            slot.is_occupied = False

        await session.commit()

    print()
    print("=" * 68)
    print("VELO PHYSICAL DEVELOPMENT DEMO READY")
    print("=" * 68)
    print(f"Test phone:       {TEST_PHONE}")
    print(f"User ID:          {user.id}")
    print(f"Wallet:           ₹{balance:.2f}")
    print()
    print(f"Start dock:       {START_DOCK_ID}  (MG Road Dock)")
    print(f"Start slot:       {START_SLOT_1_ID}  OCCUPIED")
    print(f"Demo scooter:     {vehicle.id}")
    print(f"QR code:          {vehicle.qr_code}")
    print(f"Battery:          {vehicle.battery_level}%")
    print(f"Vehicle status:   {vehicle.status}")
    print()
    print(f"Destination dock: {DEST_DOCK_ID}  (Koramangala Dock)")
    print(f"Free slots:       2")
    print()
    print("Runtime flow:")
    print("  1. Firebase login with +919876500000")
    print("  2. Request ride token at MG Road Dock")
    print("  3. Flutter displays QR")
    print("  4. ESP32-CAM scans QR")
    print("  5. Hardware POSTs /api/v1/rides/confirm")
    print("  6. Ride becomes ACTIVE")
    print("  7. End ride at Koramangala Dock")
    print("  8. Scooter is parked in a free destination slot")
    print("  9. Fare is deducted from the wallet")
    print("=" * 68)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reset the Velo physical development demo database state"
    )
    parser.add_argument(
        "--firebase-uid",
        default=None,
        help=(
            "Real Firebase UID for +919876500000. Only required if the "
            "PostgreSQL user does not already exist."
        ),
    )
    parser.add_argument(
        "--balance",
        type=float,
        default=DEV_WALLET_BALANCE,
        help="Wallet balance to seed (default: 1000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        asyncio.run(main(args.firebase_uid, args.balance))
    except Exception as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
