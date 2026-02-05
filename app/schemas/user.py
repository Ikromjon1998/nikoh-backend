from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)
    phone: str | None = None
    preferred_language: str = "ru"


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    phone: str | None
    status: str
    preferred_language: str
    email_verified: bool
    is_admin: bool = False
    verification_status: str = "unverified"
    verification_expires_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: str
    exp: int


# Admin schemas
class UserAdminResponse(BaseModel):
    id: UUID
    email: str
    phone: str | None
    status: str
    preferred_language: str
    email_verified: bool
    is_admin: bool
    verification_status: str
    verification_expires_at: datetime | None
    created_at: datetime
    last_active_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserAdminListResponse(BaseModel):
    users: list[UserAdminResponse]
    total: int
    page: int
    per_page: int


class UserBan(BaseModel):
    reason: str | None = None


class UserUnban(BaseModel):
    note: str | None = None


# Admin dashboard stats
class AdminDashboardStats(BaseModel):
    total_users: int
    verified_users: int
    pending_verifications: int
    open_reports: int


class SystemHealthStatus(BaseModel):
    database: str  # "connected" or "disconnected"
    payment_system: str  # "online" or "offline"
    auto_verification: str  # "enabled" or "disabled"


class AdminDashboardResponse(BaseModel):
    stats: AdminDashboardStats
    system_status: SystemHealthStatus
