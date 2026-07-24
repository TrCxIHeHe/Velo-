import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_by_firebase_uid(self, firebase_uid: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.firebase_uid == firebase_uid)
        )
        return result.scalar_one_or_none()

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, firebase_uid: str, phone_number: str) -> User:
        user = User(firebase_uid=firebase_uid, phone_number=phone_number)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_name(self, user_id: uuid.UUID, name: str) -> User | None:
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(name=name, updated_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await self.session.flush()
        return await self.find_by_id(user_id)


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self, user_id: uuid.UUID, token_hash: str, expires_at: datetime, family_id: uuid.UUID
    ) -> RefreshToken:
        record = RefreshToken(
            user_id=user_id, token_hash=token_hash, expires_at=expires_at, family_id=family_id
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def find_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.id == token_id).values(revoked=True)
        )
        await self.session.flush()

    async def revoke_family(self, family_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.family_id == family_id).values(revoked=True)
        )
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self.session.flush()
