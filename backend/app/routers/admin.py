from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.auth import AdminTokenOut
from app.schemas.user import AdminUserUpdate, SessionOut, UserOut
from app.services import user as user_svc

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    users = await user_svc.admin_list_users(db)
    return [UserOut.from_orm_user(u) for u in users]


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    data: AdminUserUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await user_svc.admin_update_user(user_id, data, db)
    return UserOut.from_orm_user(user)


@router.get("/sessions/{user_id}", response_model=list[SessionOut])
async def list_user_sessions(
    user_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    sessions = await user_svc.get_user_sessions(user_id, db)
    return sessions


@router.delete("/sessions/{session_id}")
async def deactivate_session(
    session_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_svc.deactivate_session(session_id, db)
    return {"detail": "Session deactivated"}


@router.get("/tokens", response_model=list[AdminTokenOut])
async def list_all_tokens(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await user_svc.admin_list_all_tokens(db)
    return [
        AdminTokenOut(
            id=token.id,
            owner_id=token.owner_id,
            owner_username=username,
            name=token.name,
            is_active=token.is_active,
            last_used_at=token.last_used_at.isoformat() if token.last_used_at else None,
            created_at=token.created_at.isoformat(),
        )
        for token, username in rows
    ]


@router.delete("/tokens/{token_id}")
async def revoke_any_token(
    token_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    await user_svc.admin_revoke_any_token(token_id, db)
    return {"detail": "Token revoked"}
