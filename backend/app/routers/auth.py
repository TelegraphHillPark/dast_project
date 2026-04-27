from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_user
from app.core.limiter import limiter
from app.core.security import create_pre_auth_token
from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    PreAuthResponse,
    RefreshRequest,
    RegisterRequest,
    TOTPEnableRequest,
    TOTPSetupResponse,
    TOTPVerifyRequest,
    TokenResponse,
)
from app.schemas.user import UserOut
from app.services import auth as auth_svc

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_svc.register_user(data, db)
    return UserOut.from_orm_user(user)


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_svc.authenticate_user(data.email, data.password, db)

    if user.totp_secret:
        pre_auth_token = create_pre_auth_token(user.id)
        return PreAuthResponse(pre_auth_token=pre_auth_token)

    return await auth_svc.create_session(user, request, db)


@router.post("/2fa/verify", response_model=TokenResponse)
@limiter.limit("10/minute")
async def verify_2fa(request: Request, data: TOTPVerifyRequest, db: AsyncSession = Depends(get_db)):
    return await auth_svc.complete_login_with_2fa(data.pre_auth_token, data.code, request, db)


@router.post("/2fa/setup", response_model=TOTPSetupResponse)
async def setup_2fa(current_user: User = Depends(get_current_user)):
    result = auth_svc.setup_totp(current_user)
    # Секрет возвращается, но ещё НЕ сохраняется — нужно подтвердить кодом
    return TOTPSetupResponse(**result)


@router.post("/2fa/enable")
async def enable_2fa(
    data: TOTPEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    setup = auth_svc.setup_totp(current_user)
    if not auth_svc.verify_totp_code(setup["secret"], data.code):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")
    current_user.totp_secret = setup["secret"]
    return {"detail": "2FA enabled"}


@router.post("/2fa/disable")
async def disable_2fa(
    data: TOTPEnableRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not current_user.totp_secret:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="2FA is not enabled")
    if not auth_svc.verify_totp_code(current_user.totp_secret, data.code):
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid TOTP code")
    current_user.totp_secret = None
    return {"detail": "2FA disabled"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    return await auth_svc.refresh_tokens(data.refresh_token, db)


@router.post("/logout")
async def logout(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    await auth_svc.logout(data.refresh_token, db)
    return {"detail": "Logged out"}


# ── OAuth ─────────────────────────────────────────────────────────────────────

@router.get("/oauth/github")
async def oauth_github_redirect():
    url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={settings.GITHUB_CLIENT_ID}"
        f"&scope=user:email"
    )
    return RedirectResponse(url)


@router.get("/oauth/github/callback", response_model=TokenResponse)
async def oauth_github_callback(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await auth_svc.oauth_github_callback(code, request, db)


@router.get("/oauth/google")
async def oauth_google_redirect(request: Request):
    redirect_uri = f"{request.base_url}api/auth/oauth/google/callback"
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=openid%20email%20profile"
    )
    return RedirectResponse(url)


@router.get("/oauth/google/callback", response_model=TokenResponse)
async def oauth_google_callback(code: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await auth_svc.oauth_google_callback(code, request, db)
