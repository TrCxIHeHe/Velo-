import json
import logging
import uuid

from app.core.exceptions import DuplicateReferenceError, InvalidWebhookSignatureError
from app.payments.gateway import RazorpayGateway
from app.payments.schemas import CreateOrderResponse
from app.wallet.service import WalletService

logger = logging.getLogger(__name__)

# Only these events actually move money into the wallet. Razorpay sends many
# other event types (order.paid also fires alongside payment.captured for the
# same transaction) — payment.captured is the single source of truth for
# "money has settled," so only it triggers a credit.
CREDITABLE_EVENT = "payment.captured"


class PaymentService:
    def __init__(self, gateway: RazorpayGateway, wallet_service: WalletService) -> None:
        self.gateway = gateway
        self.wallet_service = wallet_service

    async def create_order(self, user_id: uuid.UUID, amount: float) -> CreateOrderResponse:
        order = self.gateway.create_order(
            amount, receipt=f"topup:{user_id}:{uuid.uuid4().hex[:12]}", notes={"user_id": str(user_id)}
        )
        return CreateOrderResponse(
            order_id=order["id"],
            amount=amount,
            currency=order.get("currency", "INR"),
            key_id=self.gateway.key_id,
        )

    async def handle_webhook(self, raw_body: bytes, signature: str) -> None:
        if not self.gateway.verify_webhook_signature(raw_body, signature):
            raise InvalidWebhookSignatureError()

        event = json.loads(raw_body)
        event_type = event.get("event")
        if event_type != CREDITABLE_EVENT:
            logger.info("Ignoring Razorpay webhook event=%s (not creditable)", event_type)
            return

        payment = event["payload"]["payment"]["entity"]
        user_id_raw = (payment.get("notes") or {}).get("user_id")
        if not user_id_raw:
            logger.warning("Razorpay payment.captured with no user_id in notes: payment_id=%s", payment.get("id"))
            return

        amount_rupees = payment["amount"] / 100
        payment_id = payment["id"]

        # top_up() enforces reference_id uniqueness (checked + DB-constrained),
        # so a webhook retry (Razorpay retries on any non-2xx response) must
        # be swallowed here rather than surfaced — the payment was already
        # credited the first time this payment_id was seen.
        try:
            await self.wallet_service.top_up(
                uuid.UUID(user_id_raw), amount_rupees, reference_id=f"razorpay:{payment_id}"
            )
        except DuplicateReferenceError:
            logger.info("Razorpay webhook retry for already-credited payment_id=%s", payment_id)
