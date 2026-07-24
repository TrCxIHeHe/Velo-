import uuid
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.repository import RefreshTokenRepository, UserRepository
from app.auth.service import AuthService
from app.core.exceptions import ForbiddenError, InvalidTokenError, TokenExpiredError
from app.core.firebase import FirebaseService, get_firebase_service
from app.core.jwt import JWTService
from app.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_user_repo(session: DbSession) -> UserRepository:
    return UserRepository(session)


def get_token_repo(session: DbSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)


def get_audit_repo(session: DbSession) -> AuditLogRepository:
    return AuditLogRepository(session)


def get_jwt_service() -> JWTService:
    return JWTService()


def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    token_repo: Annotated[RefreshTokenRepository, Depends(get_token_repo)],
    firebase: Annotated[FirebaseService, Depends(get_firebase_service)],
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
    audit_repo: Annotated[AuditLogRepository, Depends(get_audit_repo)],
) -> AuthService:
    return AuthService(user_repo, token_repo, firebase, jwt, audit_repo)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_INVALID_TOKEN", "message": "Missing bearer token."},
        )
    try:
        payload = jwt.decode_access_token(credentials.credentials)
    except (InvalidTokenError, TokenExpiredError) as exc:
        raise HTTPException(
            status_code=exc.http_status,
            detail={"code": exc.code, "message": exc.message},
        )
    user_id = uuid.UUID(payload["sub"])
    user = await user_repo.find_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_INVALID_TOKEN", "message": "User not found or deactivated."},
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(role: str):
    async def checker(user: CurrentUser) -> User:
        if user.role != role:
            exc = ForbiddenError()
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": exc.message},
            )
        return user
    return checker


RequireAdmin = Annotated[User, Depends(require_role("ADMIN"))]


async def get_current_user_id(current_user: CurrentUser) -> uuid.UUID:
    return current_user.id


async def require_admin(admin_user: RequireAdmin) -> None:
    return None
