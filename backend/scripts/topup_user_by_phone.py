"""
Top up the Velo test user's wallet and write the corresponding ledger entry.

Default test user:
    +919876500000

Run from backend/:
    python scripts/topup_user_by_phone.py
    python scripts/topup_user_by_phone.py --amount 1000
    python scripts/topup_user_by_phone.py --phone +919876500000 --amount 500
"""

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.wallet import Wallet, WalletTransaction


DEFAULT_PHONE = "+919876500000"
DEFAULT_AMOUNT = 1000.0


async def top_up(phone: str, amount: float) -> None:
    if amount <= 0:
        raise ValueError("amount must be greater than 0")

    async with AsyncSessionFactory() as session:
        result = await session.execute(
            select(User).where(User.phone_number == phone)
        )
        user = result.scalar_one_or_none()

        if user is None:
            raise RuntimeError(f"No user found with phone {phone}")

        wallet_result = await session.execute(
            select(Wallet).where(Wallet.user_id == user.id)
        )
        wallet = wallet_result.scalar_one_or_none()

        if wallet is None:
            wallet = Wallet(
                user_id=user.id,
                balance=0.0,
                currency="INR",
            )
            session.add(wallet)
            await session.flush()

        old_balance = wallet.balance
        wallet.balance = round(old_balance + amount, 2)

        transaction = WalletTransaction(
            wallet_id=wallet.id,
            type="CREDIT",
            source="TOPUP",
            amount=amount,
            balance_after=wallet.balance,
            reference_id=f"manual-topup:{uuid.uuid4()}",
            note="Development/test wallet top-up",
        )
        session.add(transaction)

        await session.commit()

        print("Wallet top-up successful")
        print(f"  User:       {user.name or '(unnamed)'}")
        print(f"  Phone:      {user.phone_number}")
        print(f"  Wallet ID:  {wallet.id}")
        print(f"  Previous:   ₹{old_balance:.2f}")
        print(f"  Top-up:     ₹{amount:.2f}")
        print(f"  New balance:₹{wallet.balance:.2f}")
        print(f"  Transaction:{transaction.id}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Top up a Velo development wallet")
    parser.add_argument("--phone", default=DEFAULT_PHONE)
    parser.add_argument("--amount", type=float, default=DEFAULT_AMOUNT)
    args = parser.parse_args()

    try:
        asyncio.run(top_up(args.phone, args.amount))
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
