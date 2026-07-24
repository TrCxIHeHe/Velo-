from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    firebase_id_token: str = Field(..., description="Firebase ID token from client SDK")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., description="Raw refresh token issued at login or last refresh")


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., description="Raw refresh token to revoke")


class UpdateProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    phone_number: str
    name: str | None
    role: str
    created_at: datetime
    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    user: UserResponse


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
