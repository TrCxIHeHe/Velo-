import uuid
from datetime import datetime, timedelta, timezone

from app.audit.repository import AuditLogRepository
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.auth.schemas import SessionResponse, TokenPairResponse, UserResponse
from app.config import settings
from app.core.exceptions import (
    RefreshTokenExpiredError, RefreshTokenInvalidError, RefreshTokenReuseError,
    UserDeactivatedError, UserNotFoundError,
)
from app.core.firebase import FirebaseService
from app.core.jwt import JWTService
from app.core.security import generate_raw_token, hash_token


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _strip_tz(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class AuthService:
    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: RefreshTokenRepository,
        firebase: FirebaseService,
        jwt: JWTService,
        audit_repo: AuditLogRepository,
    ) -> None:
        self.user_repo = user_repo
        self.token_repo = token_repo
        self.firebase = firebase
        self.jwt = jwt
        self.audit_repo = audit_repo

    async def login(self, firebase_id_token: str) -> SessionResponse:
        verified = self.firebase.verify_id_token(firebase_id_token)
        firebase_uid: str = verified["uid"]
        phone_number: str = verified["phone_number"]

        user = await self.user_repo.find_by_firebase_uid(firebase_uid)
        if user is None:
            user = await self.user_repo.create(firebase_uid, phone_number)

        if not user.is_active:
            raise UserDeactivatedError()

        access_token = self.jwt.create_access_token(user.id, user.role)
        raw_refresh = generate_raw_token()
        family_id = uuid.uuid4()
        expires_at = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.token_repo.create(user.id, hash_token(raw_refresh), expires_at, family_id)
        await self.audit_repo.log(user.id, "USER_LOGIN", "user", str(user.id))

        return SessionResponse(
            access_token=access_token,
            refresh_token=raw_refresh,
            user=UserResponse.model_validate(user),
        )

    async def refresh(self, raw_refresh_token: str) -> TokenPairResponse:
        token_hash = hash_token(raw_refresh_token)
        record = await self.token_repo.find_by_hash(token_hash)
        if record is None:
            raise RefreshTokenInvalidError()
        if record.revoked:
            await self.token_repo.revoke_family(record.family_id)
            raise RefreshTokenReuseError()
        if _strip_tz(record.expires_at) < _utcnow():
            raise RefreshTokenExpiredError()

        user = await self.user_repo.find_by_id(record.user_id)
        if not user or not user.is_active:
            raise UserDeactivatedError()

        await self.token_repo.revoke(record.id)
        raw_new = generate_raw_token()
        new_expires_at = _utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.token_repo.create(user.id, hash_token(raw_new), new_expires_at, record.family_id)
        access_token = self.jwt.create_access_token(user.id, user.role)
        await self.audit_repo.log(user.id, "TOKEN_REFRESH", "refresh_token", str(record.id))
        return TokenPairResponse(access_token=access_token, refresh_token=raw_new)

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_token(raw_refresh_token)
        record = await self.token_repo.find_by_hash(token_hash)
        if record and not record.revoked:
            await self.token_repo.revoke(record.id)
            await self.audit_repo.log(record.user_id, "USER_LOGOUT", "refresh_token", str(record.id))

    async def get_me(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.user_repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError()
        return UserResponse.model_validate(user)

    async def update_name(self, user_id: uuid.UUID, name: str) -> UserResponse:
        user = await self.user_repo.update_name(user_id, name)
        if not user:
            raise UserNotFoundError()
        return UserResponse.model_validate(user)
