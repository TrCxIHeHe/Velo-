"""
Ad-hoc dev utility: top up a wallet for a user identified by phone number.

Usage from backend/ with venv active:

    python scripts/topup_user_by_phone.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionFactory
from app.models.user import User
from app.models.wallet import Wallet

PHONE = "+919876500000"
TOPUP_AMOUNT = 1000.0


async def main():
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.phone_number == PHONE))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"No user found with phone {PHONE}")
            return
        print(f"Found user: id={user.id} name={user.name} phone={user.phone_number}")

        wresult = await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        wallet = wresult.scalar_one_or_none()
        if wallet is None:
            wallet = Wallet(user_id=user.id, balance=TOPUP_AMOUNT, currency="INR")
            session.add(wallet)
            print(f"Created wallet with balance {TOPUP_AMOUNT}")
        else:
            print(f"Current balance: {wallet.balance}")
            wallet.balance += TOPUP_AMOUNT
            print(f"New balance: {wallet.balance}")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
