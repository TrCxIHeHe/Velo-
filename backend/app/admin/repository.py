"""The stats side (AdminRepository) deliberately does NOT duplicate wallet/dock
query logic. It composes the WalletRepository and DockRepository you already
built and tested, so if the ledger calculation logic ever changes, the
dashboard figures update automatically with zero admin-side code changes.

The management side (AdminUserRepository / AdminAuditRepository /
AdminRideRepository) queries User/AuditLog/Ride directly since those are
simple listing/mutation operations with no shared business logic to reuse.
"""
import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.dock.repository import DockRepository
from app.models.audit_log import AuditLog
from app.models.ride import Ride
from app.models.user import User
from app.wallet.repository import WalletRepository


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.wallet_repo = WalletRepository(session)
        self.dock_repo = DockRepository(session)


class AdminUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_users(self, skip: int = 0, limit: int = 50) -> tuple[list[User], int]:
        count = (await self.session.execute(select(func.count(User.id)))).scalar_one()
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars()), count

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def set_role(self, user_id: uuid.UUID, role: str) -> User | None:
        await self.session.execute(update(User).where(User.id == user_id).values(role=role))
        await self.session.flush()
        return await self.find_by_id(user_id)

    async def set_active(self, user_id: uuid.UUID, is_active: bool) -> User | None:
        await self.session.execute(update(User).where(User.id == user_id).values(is_active=is_active))
        await self.session.flush()
        return await self.find_by_id(user_id)


class AdminAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_logs(
        self,
        skip: int = 0,
        limit: int = 50,
        user_id: uuid.UUID | None = None,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))
        if user_id:
            query = query.where(AuditLog.user_id == user_id)
            count_query = count_query.where(AuditLog.user_id == user_id)
        if action:
            query = query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)
        total = (await self.session.execute(count_query)).scalar_one()
        result = await self.session.execute(
            query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars()), total


class AdminRideRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(
        self, skip: int = 0, limit: int = 50, status: str | None = None
    ) -> tuple[list[Ride], int]:
        query = select(Ride)
        count_query = select(func.count(Ride.id))
        if status:
            query = query.where(Ride.status == status)
            count_query = count_query.where(Ride.status == status)
        total = (await self.session.execute(count_query)).scalar_one()
        result = await self.session.execute(
            query.order_by(Ride.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars()), total
