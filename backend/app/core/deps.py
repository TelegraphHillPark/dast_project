from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, APIKeyHeader
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import TOKEN_TYPE_ACCESS, decode_token, hash_token
from app.database import get_db
from app.models.user import User, UserRole
from app.models.session import UserSession
from app.models.api_token import APIToken

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _get_user_by_id(user_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    return result.scalar_one_or_none()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    api_key: str | None = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
) -> User:
    # Попытка аутентификации по API-ключу
    if api_key:
        key_hash = hash_token(api_key)
        result = await db.execute(
            select(APIToken).where(APIToken.token_hash == key_hash, APIToken.is_active == True)
        )
        token_obj = result.scalar_one_or_none()
        if token_obj:
            from datetime import datetime, timezone
            token_obj.last_used_at = datetime.now(timezone.utc)
            user = await _get_user_by_id(token_obj.owner_id, db)
            if user:
                return user

    # Попытка аутентификации по JWT Bearer
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            if payload.get("type") != TOKEN_TYPE_ACCESS:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

            user_id: str = payload.get("sub")
            session_id: str = payload.get("sid")

            result = await db.execute(
                select(UserSession).where(
                    UserSession.id == session_id,
                    UserSession.is_active == True,
                )
            )
            session = result.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

            user = await _get_user_by_id(user_id, db)
            if user:
                return user
        except JWTError:
            pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
