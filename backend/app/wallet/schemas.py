from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    currency: str
    balance: Decimal
    created_at: datetime

    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: UUID
    wallet_id: UUID
    type: str
    amount: Decimal
    reference_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CreditRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference_id: str | None = None


class DebitRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference_id: str | None = None


class RefundRequest(BaseModel):
    amount: Decimal = Field(..., gt=0)
    reference_id: str | None = None