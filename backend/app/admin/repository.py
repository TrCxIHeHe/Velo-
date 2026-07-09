"""The Admin repository deliberately does NOT duplicate wallet/dock query
logic. It composes the WalletRepository and DockRepository you already
built and tested — same pattern the setup guide describes for Track A
calling into WalletService directly instead of re-implementing ledger math.
This means if the ledger calculation logic ever changes, the dashboard
figures update automatically with zero admin-side code changes.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.dock.repository import DockRepository
from app.wallet.repository import WalletRepository


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.wallet_repo = WalletRepository(session)
        self.dock_repo = DockRepository(session)
