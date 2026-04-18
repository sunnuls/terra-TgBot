from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.redis import get_redis
from app.core.config import settings
from app.models.user import User, AuthCredential, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, RefreshRequest, ChangePasswordRequest
from app.api.deps import get_current_user
from datetime import timedelta
import redis.asyncio as aioredis

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_TTL = settings.JWT_REFRESH_EXPIRE_DAYS * 86400


async def _get_user_role(db: AsyncSession, user_id: int) -> str:
    result = await db.execute(select(UserRole).where(UserRole.user_id == user_id))
    row = result.scalar_one_or_none()
    return row.role if row else "user"


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(AuthCredential).where(AuthCredential.login == body.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Login already taken")

    user = User(full_name=body.full_name, phone=body.phone)
    db.add(user)
    await db.flush()

    cred = AuthCredential(user_id=user.id, login=body.login, password_hash=hash_password(body.password))
    db.add(cred)
    await db.commit()
    await db.refresh(user)
    from app.services.reports_feed_chat import add_user_to_reports_feed_if_exists

    await add_user_to_reports_feed_if_exists(db, user.id)

    role = "user"
    access = create_access_token(user.id, role)
    refresh = create_refresh_token()

    redis = await get_redis()
    await redis.setex(f"refresh:{refresh}", REFRESH_TTL, str(user.id))

    return TokenResponse(access_token=access, refresh_token=refresh, user_id=user.id, role=role)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AuthCredential).where(AuthCredential.login == body.login)
    )
    cred = result.scalar_one_or_none()
    if not cred or not verify_password(body.password, cred.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    result2 = await db.execute(select(User).where(User.id == cred.user_id))
    user = result2.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Account inactive")

    role = await _get_user_role(db, user.id)
    access = create_access_token(user.id, role)
    refresh = create_refresh_token()

    redis = await get_redis()
    await redis.setex(f"refresh:{refresh}", REFRESH_TTL, str(user.id))

    return TokenResponse(access_token=access, refresh_token=refresh, user_id=user.id, role=role)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    redis = await get_redis()
    user_id_str = await redis.get(f"refresh:{body.refresh_token}")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_id = int(user_id_str)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    await redis.delete(f"refresh:{body.refresh_token}")

    role = await _get_user_role(db, user.id)
    access = create_access_token(user.id, role)
    new_refresh = create_refresh_token()
    await redis.setex(f"refresh:{new_refresh}", REFRESH_TTL, str(user.id))

    return TokenResponse(access_token=access, refresh_token=new_refresh, user_id=user.id, role=role)


@router.post("/logout")
async def logout(body: RefreshRequest):
    redis = await get_redis()
    await redis.delete(f"refresh:{body.refresh_token}")
    return {"ok": True}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AuthCredential).where(AuthCredential.user_id == current_user.id))
    cred = result.scalar_one_or_none()
    if not cred or not verify_password(body.old_password, cred.password_hash):
        raise HTTPException(status_code=400, detail="Wrong current password")

    cred.password_hash = hash_password(body.new_password)
    await db.commit()
    return {"ok": True}
