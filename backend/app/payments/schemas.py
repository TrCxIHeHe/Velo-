from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Amount in INR (rupees), not paise.")


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: float
    currency: str
    key_id: str  # Razorpay key_id — public, needed by the client SDK to open checkout
