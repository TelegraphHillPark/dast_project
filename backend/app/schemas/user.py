from datetime import datetime
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    role: UserRole
    avatar_url: str | None
    is_active: bool
    totp_enabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            totp_enabled=user.totp_secret is not None,
            created_at=user.created_at,
        )


class UserUpdate(BaseModel):
    username: str | None = None
    email: EmailStr | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class SessionOut(BaseModel):
    id: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    expires_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class AdminUserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
