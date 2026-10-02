"""
Small PostgreSQL connectivity check for the Velo backend.

Run from backend/:
    python scripts/test_db.py
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine


async def test_database(verbose: bool = False) -> bool:
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            value = result.scalar_one()

            print("Database connection: OK")
            print(f"SELECT 1: {value}")

            if verbose:
                version = await conn.execute(text("SELECT version()"))
                print(f"PostgreSQL: {version.scalar_one()}")

            return True

    except Exception as exc:
        print("Database connection: FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return False

    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Velo PostgreSQL connectivity")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print PostgreSQL server version",
    )
    args = parser.parse_args()

    ok = asyncio.run(test_database(args.verbose))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
