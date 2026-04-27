import os
import shutil
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    generate_api_token,
    hash_token,
    verify_password,
    hash_password,
)
from app.models.api_token import APIToken
from app.models.session import UserSession
from app.models.user import User
from app.schemas.user import ChangePasswordRequest, UserUpdate, AdminUserUpdate


async def get_user_sessions(user_id: str, db: AsyncSession) -> list[UserSession]:
    result = await db.execute(
        select(UserSession).where(UserSession.user_id == user_id, UserSession.is_active == True)
    )
    return result.scalars().all()


async def deactivate_session(session_id: str, db: AsyncSession, owner_id: str | None = None) -> None:
    query = select(UserSession).where(UserSession.id == session_id)
    if owner_id:
        query = query.where(UserSession.user_id == owner_id)
    result = await db.execute(query)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    session.is_active = False


async def change_password(user: User, data: ChangePasswordRequest, db: AsyncSession) -> None:
    if not verify_password(data.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    if len(data.new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")
    user.hashed_password = hash_password(data.new_password)


async def update_profile(user: User, data: UserUpdate, db: AsyncSession) -> User:
    if data.username and data.username != user.username:
        exists = await db.execute(select(User).where(User.username == data.username))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
        user.username = data.username

    if data.email and data.email != user.email:
        exists = await db.execute(select(User).where(User.email == data.email))
        if exists.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already taken")
        user.email = data.email

    return user


async def upload_avatar(user: User, file: UploadFile, db: AsyncSession) -> str:
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Only JPEG/PNG/WebP/GIF allowed")

    avatars_dir = os.path.join(settings.WORDLISTS_DIR, "..", "uploads", "avatars")
    os.makedirs(avatars_dir, exist_ok=True)

    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "jpg"
    filename = f"{user.id}.{ext}"
    path = os.path.join(avatars_dir, filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    user.avatar_url = f"/uploads/avatars/{filename}"
    return user.avatar_url


async def create_api_token(user: User, name: str, db: AsyncSession) -> tuple[APIToken, str]:
    raw_token, token_hash = generate_api_token()
    token_obj = APIToken(owner_id=user.id, name=name, token_hash=token_hash)
    db.add(token_obj)
    await db.flush()
    return token_obj, raw_token


async def get_api_tokens(user_id: str, db: AsyncSession) -> list[APIToken]:
    result = await db.execute(
        select(APIToken).where(APIToken.owner_id == user_id, APIToken.is_active == True)
    )
    return result.scalars().all()


async def revoke_api_token(token_id: str, user_id: str, db: AsyncSession) -> None:
    result = await db.execute(
        select(APIToken).where(APIToken.id == token_id, APIToken.owner_id == user_id)
    )
    token_obj = result.scalar_one_or_none()
    if not token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    token_obj.is_active = False


async def admin_list_users(db: AsyncSession) -> list[User]:
    result = await db.execute(select(User))
    return result.scalars().all()


async def admin_update_user(user_id: str, data: AdminUserUpdate, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    return user


async def admin_list_all_tokens(db: AsyncSession) -> list[tuple]:
    from app.models.user import User as UserModel
    result = await db.execute(
        select(APIToken, UserModel.username)
        .join(UserModel, UserModel.id == APIToken.owner_id)
        .order_by(APIToken.created_at.desc())
    )
    return result.all()


async def admin_revoke_any_token(token_id: str, db: AsyncSession) -> None:
    result = await db.execute(select(APIToken).where(APIToken.id == token_id))
    token_obj = result.scalar_one_or_none()
    if not token_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    token_obj.is_active = False
