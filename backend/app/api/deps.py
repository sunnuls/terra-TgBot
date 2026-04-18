from fastapi import Depends, HTTPException, status, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole
import redis.asyncio as aioredis

bearer = HTTPBearer(auto_error=False)


async def _get_user_from_token(token: str, db: AsyncSession) -> User:
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return await _get_user_from_token(credentials.credentials, db)


async def get_current_user_role(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> tuple[User, str]:
    result = await db.execute(select(UserRole).where(UserRole.user_id == user.id))
    role_row = result.scalar_one_or_none()
    role = role_row.role if role_row else "user"
    return user, role


def require_role(*allowed_roles: str):
    async def checker(
        user_and_role: tuple = Depends(get_current_user_role),
    ) -> tuple:
        user, role = user_and_role
        user_roles = {r.strip() for r in role.split(",")}
        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Role '{role}' not allowed")
        return user, role
    return checker


require_admin = require_role("admin")
require_accountant_or_admin = require_role("admin", "accountant")


async def ws_get_current_user(websocket: WebSocket, db: AsyncSession) -> User:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        raise HTTPException(status_code=401)
    return await _get_user_from_token(token, db)
