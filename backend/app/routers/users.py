from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.auth import APITokenCreate, APITokenOut, APITokenResponse
from app.schemas.user import ChangePasswordRequest, SessionOut, UserOut, UserUpdate
from app.services import user as user_svc

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.from_orm_user(current_user)


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await user_svc.update_profile(current_user, data, db)
    return UserOut.from_orm_user(user)


@router.post("/me/change-password")
async def change_password(
    data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await user_svc.change_password(current_user, data, db)
    return {"detail": "Password changed"}


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    url = await user_svc.upload_avatar(current_user, file, db)
    return {"avatar_url": url}


@router.get("/me/sessions", response_model=list[SessionOut])
async def my_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await user_svc.get_user_sessions(current_user.id, db)


@router.delete("/me/sessions/{session_id}")
async def revoke_my_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await user_svc.deactivate_session(session_id, db, owner_id=current_user.id)
    return {"detail": "Session revoked"}


@router.get("/me/tokens", response_model=list[APITokenOut])
async def my_tokens(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    tokens = await user_svc.get_api_tokens(current_user.id, db)
    return [
        APITokenOut(
            id=t.id,
            name=t.name,
            is_active=t.is_active,
            last_used_at=t.last_used_at.isoformat() if t.last_used_at else None,
            created_at=t.created_at.isoformat(),
        )
        for t in tokens
    ]


@router.post("/me/tokens", response_model=APITokenResponse)
async def create_token(
    data: APITokenCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    token_obj, raw_token = await user_svc.create_api_token(current_user, data.name, db)
    return APITokenResponse(
        id=token_obj.id,
        name=token_obj.name,
        token=raw_token,
        created_at=token_obj.created_at.isoformat(),
    )


@router.delete("/me/tokens/{token_id}")
async def revoke_token(
    token_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await user_svc.revoke_api_token(token_id, current_user.id, db)
    return {"detail": "Token revoked"}
