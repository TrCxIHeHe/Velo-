from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.repository import AuditLogRepository
from app.auth.dependencies import CurrentUser
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.database import get_db
from app.payments.gateway import RazorpayGateway, get_razorpay_gateway
from app.payments.schemas import CreateOrderRequest
from app.payments.service import PaymentService
from app.wallet.repository import WalletRepository
from app.wallet.service import WalletService

router = APIRouter(prefix="/payments", tags=["payments"])


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    gateway: Annotated[RazorpayGateway, Depends(get_razorpay_gateway)],
) -> PaymentService:
    wallet_service = WalletService(WalletRepository(session), AuditLogRepository(session))
    return PaymentService(gateway, wallet_service)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]


@router.post("/orders")
@limiter.limit("10/minute")
async def create_order(
    request: Request, body: CreateOrderRequest, current_user: CurrentUser, service: PaymentServiceDep
):
    """Create a Razorpay order for wallet top-up. The client opens Razorpay
    Checkout with the returned order_id/key_id; the wallet is credited only
    once the /payments/webhook receives a verified payment.captured event —
    never directly from this endpoint, since the client can't be trusted to
    honestly report its own payment outcome."""
    try:
        order = await service.create_order(current_user.id, body.amount)
        return success_response(order.model_dump(), status_code=201)
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)


@router.post("/webhook")
async def razorpay_webhook(
    request: Request, service: PaymentServiceDep, x_razorpay_signature: Annotated[str, Header()] = ""
):
    """Called by Razorpay's servers, not the app — no user auth, authenticity
    comes entirely from the HMAC signature over the raw request body. Not
    rate-limited: a real high-volume merchant account would need this to
    scale with payment volume, and it's already protected by signature
    verification rather than caller identity."""
    raw_body = await request.body()
    try:
        await service.handle_webhook(raw_body, x_razorpay_signature)
        return success_response({"status": "ok"})
    except AppException as exc:
        return error_response(exc.code, exc.message, exc.http_status)
