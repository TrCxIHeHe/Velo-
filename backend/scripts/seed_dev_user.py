"""
Creates one fake user row so wallet/dock endpoints have something real to
attach to via foreign keys. Run this once after `alembic upgrade head`,
any time you reset the database, or whenever you want a fresh test user.

Usage (from backend/, venv active):
    python scripts/seed_dev_user.py

Prints the user's id — use that exact value as your X-Debug-User-Id header.
"""
import asyncio
import sys
import uuid
from pathlib import Path

# Running "python scripts\seed_dev_user.py" puts this file's own folder
# (scripts\) on sys.path, NOT backend\ — so `import app...` fails with
# "ModuleNotFoundError: No module named 'app'", the same root cause as the
# earlier Alembic issue, just without Alembic's prepend_sys_path fix to lean
# on. This line adds backend\ (this script's parent folder) to sys.path
# manually, before the app import below, so it works no matter how or from
# where you invoke this file.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import AsyncSessionFactory  # noqa: E402
from app.models.user import User  # noqa: E402

DEV_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


async def main():
    async with AsyncSessionFactory() as session:
        existing = await session.get(User, DEV_USER_ID)
        if existing:
            print(f"Dev user already exists: {existing.id}")
            return

        user = User(
            id=DEV_USER_ID,
            firebase_uid="debug-uid-1",
            phone_number="+910000000001",
            name="Debug User",
            role="USER",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"Created dev user: {user.id}")
        print(f'Use this header on requests: X-Debug-User-Id: {user.id}')


if __name__ == "__main__":
    asyncio.run(main())