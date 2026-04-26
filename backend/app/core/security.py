import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"
TOKEN_TYPE_PRE_AUTH = "pre_auth"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _create_token(data: dict, token_type: str, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload.update({
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
    })
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_access_token(user_id: str, session_id: str) -> str:
    return _create_token(
        {"sub": user_id, "sid": session_id},
        TOKEN_TYPE_ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str, session_id: str) -> str:
    return _create_token(
        {"sub": user_id, "sid": session_id},
        TOKEN_TYPE_REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def create_pre_auth_token(user_id: str) -> str:
    """Короткоживущий токен после проверки пароля — до подтверждения 2FA."""
    return _create_token(
        {"sub": user_id},
        TOKEN_TYPE_PRE_AUTH,
        timedelta(minutes=5),
    )


def decode_token(token: str) -> dict:
    """Декодирует JWT, бросает JWTError при невалидном токене."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])


def hash_token(token: str) -> str:
    """SHA-256 хэш токена для хранения в БД."""
    return hashlib.sha256(token.encode()).hexdigest()


def generate_api_token() -> tuple[str, str]:
    """Возвращает (raw_token, hash). raw_token показывается пользователю один раз."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_token(raw)
