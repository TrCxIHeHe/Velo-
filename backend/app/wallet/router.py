import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser, require_role
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.database import get_db
from app.wallet.repository import WalletRepository
from app.wallet.schemas import AdminAdjustRequest, TopUpRequest
from app.wallet.service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


def get_wallet_service(session: Annotated[AsyncSession, Depends(get_db)]) -> WalletService:
    return WalletService(WalletRepository(session), AuditLogRepository(session))


WalletServiceDep = Annotated[WalletService, Depends(get_wallet_service)]


@router.get("")
async def get_balance(current_user: CurrentUser, service: WalletServiceDep):
    try:
        wallet = await service.get_balance(current_user.id)
        return success_response(wallet.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/topup")
@limiter.limit("10/minute")
async def top_up(request: Request, body: TopUpRequest, current_user: CurrentUser, service: WalletServiceDep):
    try:
        wallet = await service.top_up(current_user.id, body.amount, body.reference_id)
        return success_response(wallet.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.get("/transactions")
async def list_transactions(
    current_user: CurrentUser, service: WalletServiceDep, skip: int = 0, limit: int = 20
):
    result = await service.list_transactions(current_user.id, skip, limit)
    return success_response(result.model_dump())


@router.post("/admin/adjust", dependencies=[Depends(require_role("ADMIN"))])
async def admin_adjust(body: AdminAdjustRequest, admin_user: CurrentUser, service: WalletServiceDep):
    try:
        wallet = await service.admin_adjust(
            body.user_id, body.amount, body.note, body.reference_id, actor_id=admin_user.id
        )
        return success_response(wallet.model_dump())
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
