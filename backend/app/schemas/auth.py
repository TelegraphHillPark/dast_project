from pydantic import BaseModel, EmailStr, field_validator
import re


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_-]{3,64}$", v):
            raise ValueError("Username must be 3-64 chars: letters, digits, _ or -")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TOTPVerifyRequest(BaseModel):
    pre_auth_token: str
    code: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class PreAuthResponse(BaseModel):
    requires_2fa: bool = True
    pre_auth_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_uri: str


class TOTPEnableRequest(BaseModel):
    code: str


class APITokenCreate(BaseModel):
    name: str


class APITokenResponse(BaseModel):
    id: str
    name: str
    token: str
    created_at: str


class APITokenOut(BaseModel):
    id: str
    name: str
    is_active: bool
    last_used_at: str | None
    created_at: str

    model_config = {"from_attributes": True}
