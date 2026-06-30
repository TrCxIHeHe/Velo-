from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import CurrentUser, get_auth_service
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    UpdateProfileRequest,
)
from app.auth.service import AuthService
from app.core.exceptions import AppException
from app.core.response import error_response, success_response

router = APIRouter(prefix="/auth", tags=["auth"])

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def _handle_app_exception(exc: AppException):
    return error_response(exc.code, exc.message, exc.http_status)


# ── POST /auth/login ──────────────────────────────────────────────────────────

@router.post("/login")
async def login(body: LoginRequest, service: AuthServiceDep):
    """Exchange a Firebase ID token for an access + refresh token pair.

    The phone number is extracted from the Firebase token server-side.
    The client must never send the phone number directly.
    """
    try:
        session = await service.login(body.firebase_id_token)
        return success_response(session.model_dump(), status_code=200)
    except AppException as exc:
        return _handle_app_exception(exc)


# ── POST /auth/refresh ────────────────────────────────────────────────────────

@router.post("/refresh")
async def refresh(body: RefreshRequest, service: AuthServiceDep):
    """Rotate the refresh token and return a new access + refresh token pair.

    Both tokens are replaced. The client must store the new refresh token
    immediately and discard the old one.

    If the presented token has already been used (reuse attack), the entire
    session family is revoked and AUTH_REFRESH_REUSE is returned.
    """
    try:
        pair = await service.refresh(body.refresh_token)
        return success_response(pair.model_dump())
    except AppException as exc:
        return _handle_app_exception(exc)


# ── POST /auth/logout ─────────────────────────────────────────────────────────

@router.post("/logout")
async def logout(body: LogoutRequest, service: AuthServiceDep):
    """Revoke the current refresh token.

    Idempotent — always returns 200 so the client can treat logout as
    unconditionally successful regardless of token state.
    """
    await service.logout(body.refresh_token)
    return success_response({"message": "Logged out successfully."})


# ── GET /auth/me ──────────────────────────────────────────────────────────────

@router.get("/me")
async def get_me(current_user: CurrentUser, service: AuthServiceDep):
    """Return the authenticated user's profile."""
    try:
        profile = await service.get_me(current_user.id)
        return success_response(profile.model_dump())
    except AppException as exc:
        return _handle_app_exception(exc)


# ── PATCH /auth/me ────────────────────────────────────────────────────────────

@router.patch("/me")
async def update_me(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    service: AuthServiceDep,
):
    """Update the authenticated user's display name."""
    try:
        profile = await service.update_name(current_user.id, body.name)
        return success_response(profile.model_dump())
    except AppException as exc:
        return _handle_app_exception(exc)
