from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_admin
from app.database import get_db
from app.models.user import User
from app.schemas.auth import AdminTokenOut
from app.schemas.user import AdminSessionOut, AdminUserUpdate, SessionOut, UserOut
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


@router.get("/sessions", response_model=list[AdminSessionOut])
async def list_all_sessions(
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select as _select
    from app.models.session import UserSession
    from app.models.user import User as UserModel
    rows = await db.execute(
        _select(UserSession, UserModel.username)
        .join(UserModel, UserModel.id == UserSession.user_id)
        .where(UserSession.is_active == True)
        .order_by(UserSession.created_at.desc())
    )
    return [
        AdminSessionOut(
            id=s.id,
            user_id=s.user_id,
            username=username,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at,
            expires_at=s.expires_at,
        )
        for s, username in rows
    ]


@router.get("/sessions/{user_id}", response_model=list[SessionOut])
async def list_user_sessions(
    user_id: str,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    return await user_svc.get_user_sessions(user_id, db)


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
