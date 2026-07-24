from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class UserListResponse(BaseModel):
    items: list[dict]
    total: int


class SetUserRoleRequest(BaseModel):
    role: str  # USER | ADMIN


class SetUserActiveRequest(BaseModel):
    is_active: bool


class AuditLogResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    meta: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
