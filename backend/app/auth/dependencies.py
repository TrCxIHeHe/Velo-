import uuid
from typing import Annotated

from fastapi import Depends
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

# ── Database & Repositories ───────────────────────────────────────────────────

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_user_repo(session: DbSession) -> UserRepository:
    return UserRepository(session)


def get_token_repo(session: DbSession) -> RefreshTokenRepository:
    return RefreshTokenRepository(session)


def get_audit_repo(session: DbSession) -> AuditLogRepository:
    return AuditLogRepository(session)


# ── Core Services (stateless singletons) ─────────────────────────────────────

def get_jwt_service() -> JWTService:
    return JWTService()


# ── Auth Service ──────────────────────────────────────────────────────────────

def get_auth_service(
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    token_repo: Annotated[RefreshTokenRepository, Depends(get_token_repo)],
    firebase: Annotated[FirebaseService, Depends(get_firebase_service)],
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
    audit_repo: Annotated[AuditLogRepository, Depends(get_audit_repo)],
) -> AuthService:
    return AuthService(user_repo, token_repo, firebase, jwt, audit_repo)


# ── Route Protection ──────────────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    user_repo: Annotated[UserRepository, Depends(get_user_repo)],
    jwt: Annotated[JWTService, Depends(get_jwt_service)],
) -> User:
    """Decode JWT and return the active User. Raises 401 on any failure —
    missing, malformed, invalid, or expired token — per common.md's
    frozen contract (all three cases are specified as 401 Unauthorized)."""
    from fastapi import HTTPException

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
    """Factory for role-based guards. Usage: Depends(require_role('ADMIN'))"""

    async def checker(user: CurrentUser) -> User:
        if user.role != role:
            exc = ForbiddenError()
            from fastapi import HTTPException
            raise HTTPException(
                status_code=exc.http_status,
                detail={"code": exc.code, "message": exc.message},
            )
        return user

    return checker


RequireAdmin = Annotated[User, Depends(require_role("ADMIN"))]


# ── Compatibility adapters for Track B routers (wallet/dock/admin) ───────────
# These modules were built against a temporary dev-only stub
# (app.dependencies.get_current_user_id / require_admin, header-based, no
# verification). This wiring replaces that stub with the real auth flow above
# without changing any wallet/dock/admin business logic.

async def get_current_user_id(current_user: CurrentUser) -> uuid.UUID:
    return current_user.id


async def require_admin(admin_user: RequireAdmin) -> None:
    return None
