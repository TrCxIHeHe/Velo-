from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class TopUpRequest(BaseModel):
    amount: float = Field(..., gt=0)
    reference_id: str | None = Field(default=None, max_length=128)


class AdminAdjustRequest(BaseModel):
    user_id: UUID
    amount: float  # positive = credit, negative = debit
    note: str | None = Field(default=None, max_length=512)
    reference_id: str | None = Field(default=None, max_length=128)


class WalletResponse(BaseModel):
    id: UUID
    user_id: UUID
    balance: float
    currency: str
    updated_at: datetime
    model_config = {"from_attributes": True}


class TransactionResponse(BaseModel):
    id: UUID
    type: str
    source: str
    amount: float
    balance_after: float
    reference_id: str | None
    note: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
