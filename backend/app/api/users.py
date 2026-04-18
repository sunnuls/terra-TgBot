from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.database import get_db
from app.models.user import User, UserRole, PushToken
from app.schemas.user import UserOut, UserUpdate, UserAdminUpdate, UserListItem
from app.api.deps import get_current_user, get_current_user_role, require_admin

router = APIRouter(prefix="/users", tags=["users"])


async def _build_user_out(user: User, db: AsyncSession) -> UserOut:
    result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    role_row = result.scalar_one_or_none()
    role = role_row.role if role_row else "user"
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        username=user.username,
        phone=user.phone,
        tz=user.tz,
        is_active=user.is_active,
        role=role,
        created_at=user.created_at,
    )


@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await _build_user_out(current_user, db)


@router.patch("/me", response_model=UserOut)
async def update_me(
    body: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name
    if body.phone is not None:
        current_user.phone = body.phone
    if body.tz is not None:
        current_user.tz = body.tz
    await db.commit()
    await db.refresh(current_user)
    return await _build_user_out(current_user, db)


@router.post("/me/push-token")
async def register_push_token(
    token: str,
    platform: str = "unknown",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PushToken).where(PushToken.token == token))
    existing = result.scalar_one_or_none()
    if not existing:
        pt = PushToken(user_id=current_user.id, token=token, platform=platform)
        db.add(pt)
        await db.commit()
    return {"ok": True}


@router.get("/online-count")
async def get_online_count(admin=Depends(require_admin)):
    from app.realtime.chat_hub import connections
    online_users: set[int] = set()
    for room_connections in connections.values():
        online_users.update(room_connections.keys())
    return {"count": len(online_users)}


@router.get("", response_model=list[UserListItem])
async def list_users(
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
):
    result = await db.execute(
        select(User).where(User.is_active == True).offset(skip).limit(limit).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    items = []
    for u in users:
        r = await db.execute(select(UserRole).where(UserRole.user_id == u.id))
        role_row = r.scalar_one_or_none()
        items.append(UserListItem(
            id=u.id,
            full_name=u.full_name,
            username=u.username,
            phone=u.phone,
            role=role_row.role if role_row else "user",
            is_active=u.is_active,
            created_at=u.created_at,
        ))
    return items


@router.patch("/{user_id}", response_model=UserOut)
async def admin_update_user(
    user_id: int,
    body: UserAdminUpdate,
    admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if body.full_name is not None:
        user.full_name = body.full_name
    if body.is_active is not None:
        user.is_active = body.is_active

    if body.role is not None:
        r = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
        role_row = r.scalar_one_or_none()
        if role_row:
            role_row.role = body.role
        else:
            db.add(UserRole(user_id=user_id, role=body.role))

    await db.commit()
    await db.refresh(user)
    return await _build_user_out(user, db)
