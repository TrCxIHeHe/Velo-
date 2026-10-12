"""
DEVELOPMENT / OPERATIONS TOOL — recover a stuck ride through the validated flow.

Unlike scripts/cancel_stuck_ride.py (raw table edits), this runs the same
RideService code as the app and the admin API (POST /admin/rides/{id}/recover):

* PENDING ride -> CANCELLED
* ACTIVE ride  -> COMPLETED at an explicit destination dock: configured fare,
  free slot, wallet debit, scooter parked. It is never just marked cancelled.
* Refuses (changing nothing) if vehicle/slot records are inconsistent, and
  prints what to check. Every recovery is written to the audit log.

Run from backend/ (never in production; use the admin API there):

    python scripts/recover_ride.py --phone +919876500000 --action complete --dock "Koramangala Dock" \\
        --reason "dev: scooter never docked" --admin-phone +919876500099
    python scripts/recover_ride.py --ride-id <uuid> --action cancel_pending \\
        --reason "dev: stale qr" --admin-phone +919876500099

--admin-phone must belong to an existing user with role ADMIN (recorded as the actor).
"""
import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import desc, select

from app.audit.repository import AuditLogRepository
from app.config import settings
from app.core.exceptions import AppException
from app.database import AsyncSessionFactory
from app.dock.repository import DockRepository, VehicleRepository
from app.models import Dock, Ride, User
from app.ride.repository import RideRepository
from app.ride.service import RideService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService


async def run(args) -> None:
    async with AsyncSessionFactory() as s:
        admin = (await s.execute(select(User).where(User.phone_number == args.admin_phone))).scalar_one_or_none()
        if admin is None or admin.role != "ADMIN":
            raise SystemExit(f"ERROR: {args.admin_phone} is not an existing ADMIN user")

        if args.ride_id:
            ride_id = uuid.UUID(args.ride_id)
        else:
            user = (await s.execute(select(User).where(User.phone_number == args.phone))).scalar_one_or_none()
            if user is None:
                raise SystemExit(f"ERROR: no user with phone {args.phone}")
            ride = (await s.execute(
                select(Ride).where(Ride.user_id == user.id, Ride.status.in_(["PENDING", "ACTIVE"]))
                .order_by(desc(Ride.created_at)).limit(1))).scalar_one_or_none()
            if ride is None:
                raise SystemExit("No PENDING/ACTIVE ride found for that user.")
            ride_id = ride.id

        dock_id = None
        if args.dock:
            try:
                dock_id = uuid.UUID(args.dock)
            except ValueError:
                docks = (await s.execute(select(Dock).where(Dock.name == args.dock))).scalars().all()
                if len(docks) != 1:
                    raise SystemExit(f"ERROR: expected one dock named {args.dock!r}, found {len(docks)}")
                dock_id = docks[0].id

        svc = RideService(
            RideRepository(s), DockRepository(s), VehicleRepository(s),
            WalletService(WalletRepository(s), AuditLogRepository(s)), AuditLogRepository(s),
        )
        try:
            result = await svc.recover_ride(admin.id, ride_id, args.action, dock_id, args.reason)
        except AppException as exc:
            raise SystemExit(f"RECOVERY REFUSED [{exc.code}]: {exc.message}\nNothing was changed.")
        print(f"Ride {result.id} -> {result.status}"
              + (f", fare {result.fare_currency} {result.fare_amount}" if result.fare_amount else ""))


def main() -> None:
    if settings.ENVIRONMENT == "production":
        raise SystemExit("Refusing to run in production: use POST /api/v1/admin/rides/{id}/recover.")
    p = argparse.ArgumentParser(description="Recover a stuck ride via the validated completion flow")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ride-id")
    g.add_argument("--phone", help="recover the user's newest PENDING/ACTIVE ride")
    p.add_argument("--action", required=True, choices=["complete", "cancel_pending"])
    p.add_argument("--dock", help="destination dock name or UUID (required for ACTIVE rides)")
    p.add_argument("--reason", required=True)
    p.add_argument("--admin-phone", required=True)
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
