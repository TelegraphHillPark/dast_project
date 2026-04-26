from datetime import datetime, timedelta, timezone

import httpx
import pyotp
from fastapi import HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import (
    TOKEN_TYPE_PRE_AUTH,
    TOKEN_TYPE_REFRESH,
    create_access_token,
    create_pre_auth_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.session import UserSession
from app.models.user import User, UserRole
from app.schemas.auth import RegisterRequest, TokenResponse


async def register_user(data: RegisterRequest, db: AsyncSession) -> User:
    existing = await db.execute(
        select(User).where((User.email == data.email) | (User.username == data.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email or username already taken")

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        role=UserRole.user,
    )
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(email: str, password: str, db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == email, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


async def create_session(user: User, request: Request, db: AsyncSession) -> TokenResponse:
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    session = UserSession(
        user_id=user.id,
        token_hash="placeholder",
        user_agent=request.headers.get("user-agent", "")[:512],
        ip_address=request.client.host if request.client else None,
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()

    access_token = create_access_token(user.id, session.id)
    refresh_token = create_refresh_token(user.id, session.id)
    session.token_hash = hash_token(refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


async def refresh_tokens(refresh_token: str, db: AsyncSession) -> TokenResponse:
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if payload.get("type") != TOKEN_TYPE_REFRESH:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    token_hash = hash_token(refresh_token)
    result = await db.execute(
        select(UserSession).where(UserSession.token_hash == token_hash, UserSession.is_active == True)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        session.is_active = False
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    new_refresh = create_refresh_token(session.user_id, session.id)
    session.token_hash = hash_token(new_refresh)
    access_token = create_access_token(session.user_id, session.id)

    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


async def logout(refresh_token: str, db: AsyncSession) -> None:
    try:
        payload = decode_token(refresh_token)
        session_id = payload.get("sid")
        result = await db.execute(select(UserSession).where(UserSession.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            session.is_active = False
    except JWTError:
        pass


def setup_totp(user: User) -> dict:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    qr_uri = totp.provisioning_uri(name=user.email, issuer_name="DAST Analyzer")
    return {"secret": secret, "qr_uri": qr_uri}


def verify_totp_code(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


async def complete_login_with_2fa(pre_auth_token: str, code: str, request: Request, db: AsyncSession) -> TokenResponse:
    try:
        payload = decode_token(pre_auth_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid pre-auth token")

    if payload.get("type") != TOKEN_TYPE_PRE_AUTH:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    result = await db.execute(select(User).where(User.id == payload["sub"], User.is_active == True))
    user = result.scalar_one_or_none()
    if not user or not user.totp_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid request")

    if not verify_totp_code(user.totp_secret, code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid TOTP code")

    return await create_session(user, request, db)


async def oauth_github_callback(code: str, request: Request, db: AsyncSession) -> TokenResponse:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={"client_id": settings.GITHUB_CLIENT_ID, "client_secret": settings.GITHUB_CLIENT_SECRET, "code": code},
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="GitHub OAuth failed")

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        gh_user = user_resp.json()

        email_resp = await client.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        emails = email_resp.json()
        primary_email = next((e["email"] for e in emails if e.get("primary") and e.get("verified")), None)
        if not primary_email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No verified email on GitHub account")

    return await _get_or_create_oauth_user(primary_email, gh_user.get("login", ""), request, db)


async def oauth_google_callback(code: str, request: Request, db: AsyncSession) -> TokenResponse:
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{request.base_url}api/auth/oauth/google/callback",
            },
        )
        token_data = token_resp.json()
        if "error" in token_data:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google OAuth failed")

        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        g_user = user_resp.json()

    return await _get_or_create_oauth_user(g_user["email"], g_user.get("name", "").replace(" ", "_"), request, db)


async def _get_or_create_oauth_user(email: str, suggested_username: str, request: Request, db: AsyncSession) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        username = suggested_username[:64] or email.split("@")[0]
        # Ensure username uniqueness
        base = username
        counter = 1
        while True:
            exists = await db.execute(select(User).where(User.username == username))
            if not exists.scalar_one_or_none():
                break
            username = f"{base}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(pyotp.random_base32()),
            role=UserRole.user,
        )
        db.add(user)
        await db.flush()

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    return await create_session(user, request, db)
