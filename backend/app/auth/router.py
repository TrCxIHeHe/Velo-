from typing import Annotated
from fastapi import APIRouter, Depends
from app.auth.dependencies import CurrentUser, get_auth_service
from app.auth.schemas import LoginRequest, LogoutRequest, RefreshRequest, UpdateProfileRequest
from app.auth.service import AuthService
from app.core.exceptions import AppException
from app.core.response import error_response, success_response

router = APIRouter(prefix="/auth", tags=["auth"])
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post("/login")
async def login(body: LoginRequest, service: AuthServiceDep):
    try:
        session = await service.login(body.firebase_id_token)
        return success_response(session.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/refresh")
async def refresh(body: RefreshRequest, service: AuthServiceDep):
    try:
        pair = await service.refresh(body.refresh_token)
        return success_response(pair.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/logout")
async def logout(body: LogoutRequest, service: AuthServiceDep):
    await service.logout(body.refresh_token)
    return success_response({"message": "Logged out successfully."})


@router.get("/me")
async def get_me(current_user: CurrentUser, service: AuthServiceDep):
    try:
        profile = await service.get_me(current_user.id)
        return success_response(profile.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.patch("/me")
async def update_me(body: UpdateProfileRequest, current_user: CurrentUser, service: AuthServiceDep):
    try:
        profile = await service.update_name(current_user.id, body.name)
        return success_response(profile.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
