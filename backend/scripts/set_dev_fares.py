"""
DEVELOPMENT ONLY — set dock-pair fares for local end-to-end testing.

These are TEST VALUES, not production pricing. The amount is mandatory on
purpose: this script never invents a price. In production, manage tariffs with
the admin API instead (POST/PATCH /api/v1/admin/dock-fares).

Run from backend/:

    # list current docks and fares
    python scripts/set_dev_fares.py --list

    # one directed pair (A -> B only; B -> A stays unconfigured)
    python scripts/set_dev_fares.py --origin "MG Road Dock" --destination "Koramangala Dock" --amount 20

    # both directions, independently priced
    python scripts/set_dev_fares.py --origin "MG Road Dock" --destination "Koramangala Dock" --amount 20 \\
        --reverse-amount 25

    # every directed pair between all active docks at one flat TEST amount
    python scripts/set_dev_fares.py --all-pairs --amount 20

Existing rows are updated (amount/currency/active) rather than duplicated.
--origin/--destination accept a dock name or a dock UUID.
"""
import argparse
import asyncio
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionFactory
from app.models import Dock, DockPairFare
from app.pricing.repository import DockPairFareRepository


def _amount(raw: str) -> Decimal:
    try:
        value = Decimal(raw).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise SystemExit(f"ERROR: invalid amount {raw!r}")
    if value <= 0:
        raise SystemExit("ERROR: amount must be greater than zero")
    return value


async def _resolve(session, ref: str) -> Dock:
    try:
        dock = await session.get(Dock, uuid.UUID(ref))
        if dock:
            return dock
    except ValueError:
        pass
    docks = (await session.execute(select(Dock).where(Dock.name == ref))).scalars().all()
    if len(docks) != 1:
        raise SystemExit(f"ERROR: expected exactly one dock matching {ref!r}, found {len(docks)}")
    return docks[0]


async def _upsert(session, origin: Dock, dest: Dock, amount: Decimal, currency: str) -> None:
    repo = DockPairFareRepository(session)
    existing = await repo.find_by_pair(origin.id, dest.id)
    if existing:
        await repo.update(existing.id, amount=amount, currency=currency, is_active=True)
        verb = "updated"
    else:
        await repo.create(origin.id, dest.id, amount, currency, True)
        verb = "created"
    print(f"  {verb}: {origin.name} -> {dest.name} = {currency} {amount}  (DEV TEST VALUE)")


async def run(args) -> None:
    async with AsyncSessionFactory() as session:
        if args.list:
            docks = (await session.execute(select(Dock).order_by(Dock.name))).scalars().all()
            names = {d.id: d.name for d in docks}
            print("Docks:")
            for d in docks:
                print(f"  {d.id}  {d.name}  active={d.is_active}")
            fares = (await session.execute(select(DockPairFare))).scalars().all()
            print("Fares (directed):" if fares else "Fares: none configured")
            for f in fares:
                print(f"  {names.get(f.origin_dock_id)} -> {names.get(f.destination_dock_id)} = "
                      f"{f.currency} {f.amount} active={f.is_active}")
            return

        if args.amount is None:
            raise SystemExit("ERROR: --amount is required (this script never invents a price)")
        amount, currency = _amount(args.amount), args.currency.upper()

        if args.all_pairs:
            docks = (await session.execute(select(Dock).where(Dock.is_active.is_(True)))).scalars().all()
            for o in docks:
                for d in docks:
                    if o.id != d.id:
                        await _upsert(session, o, d, amount, currency)
        else:
            if not (args.origin and args.destination):
                raise SystemExit("ERROR: give --origin and --destination, or --all-pairs")
            o, d = await _resolve(session, args.origin), await _resolve(session, args.destination)
            if o.id == d.id:
                raise SystemExit("ERROR: origin and destination must differ")
            await _upsert(session, o, d, amount, currency)
            if args.reverse_amount is not None:
                await _upsert(session, d, o, _amount(args.reverse_amount), currency)
        await session.commit()


def main() -> None:
    if settings.ENVIRONMENT == "production":
        raise SystemExit("Refusing to run in production: use the admin API (/api/v1/admin/dock-fares).")
    p = argparse.ArgumentParser(description="DEV ONLY: set dock-pair fares (explicit amount required)")
    p.add_argument("--list", action="store_true")
    p.add_argument("--origin")
    p.add_argument("--destination")
    p.add_argument("--amount", help="fare for origin -> destination (required, never defaulted)")
    p.add_argument("--reverse-amount", help="optional separate fare for destination -> origin")
    p.add_argument("--currency", default="INR")
    p.add_argument("--all-pairs", action="store_true", help="every directed pair of active docks")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
