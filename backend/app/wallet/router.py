from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.database import get_db
from app.response import error_response, success_response
from app.wallet.repository import WalletRepository
from app.wallet.schemas import CreditRequest, DebitRequest, RefundRequest
from app.wallet.service import WalletService

# TODO: replace with real get_current_user dependency from app.auth once wired in
def get_current_user_id() -> UUID:
    raise NotImplementedError("Wire this to app.auth.dependencies.get_current_user")


router = APIRouter(prefix="/wallet", tags=["wallet"])


def get_wallet_service(session: AsyncSession = Depends(get_db)) -> WalletService:
    return WalletService(WalletRepository(session))


@router.get("")
async def get_wallet(
    user_id: UUID = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        wallet = await service.get_wallet(user_id)
        return success_response(wallet)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.get("/transactions")
async def list_transactions(
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        txns = await service.get_transactions(user_id, limit, offset)
        return success_response(txns)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.post("/credit")
async def credit_wallet(
    body: CreditRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        txn = await service.credit(user_id, body.amount, body.reference_id)
        return success_response(txn, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.post("/debit")
async def debit_wallet(
    body: DebitRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        txn = await service.debit(user_id, body.amount, body.reference_id)
        return success_response(txn, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)


@router.post("/refund")
async def refund_wallet(
    body: RefundRequest,
    user_id: UUID = Depends(get_current_user_id),
    service: WalletService = Depends(get_wallet_service),
):
    try:
        txn = await service.refund(user_id, body.amount, body.reference_id)
        return success_response(txn, status_code=201)
    except AppException as e:
        return error_response(e.code, e.message, e.http_status)