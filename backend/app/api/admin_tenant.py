"""Админ: название компании и пригласительные ссылки."""

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.config import settings
from app.models.tenant import InviteLink, TenantSettings
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.schemas.tenant import CompanyProfileOut, InviteLinkCreate, InviteLinkOut

router = APIRouter(prefix="/admin", tags=["admin"])


def _join_base_url() -> str:
    """Базовый URL для ссылок-приглашений (веб). Можно задать PUBLIC_JOIN_BASE_URL в .env."""
    return (settings.PUBLIC_JOIN_BASE_URL or "").rstrip("/")


@router.get("/company", response_model=CompanyProfileOut)
async def get_company_profile(
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    _user, _role = admin
    result = await db.execute(select(TenantSettings).where(TenantSettings.id == 1))
    row = result.scalar_one_or_none()
    if not row:
        return CompanyProfileOut(company_name="")
    return CompanyProfileOut(company_name=row.company_name or "")


@router.post("/invite-links", response_model=InviteLinkOut, status_code=201)
async def create_invite_link(
    body: InviteLinkCreate,
    db: AsyncSession = Depends(get_db),
    admin=Depends(require_admin),
):
    user, _role = admin
    if not body.is_permanent:
        if not body.duration_hours:
            raise HTTPException(
                status_code=400,
                detail="Для временной ссылки укажите duration_hours",
            )

    now = datetime.now(timezone.utc)
    if body.is_permanent:
        expires_at = None
    else:
        expires_at = now + timedelta(hours=body.duration_hours or 0)

    token = secrets.token_urlsafe(32)[:48]

    link = InviteLink(
        token=token,
        company_name=body.company_name.strip(),
        is_permanent=body.is_permanent,
        expires_at=expires_at,
        max_visits=body.max_visits,
        created_by=user.id,
    )
    db.add(link)

    ts = await db.execute(select(TenantSettings).where(TenantSettings.id == 1))
    tenant = ts.scalar_one_or_none()
    if tenant:
        tenant.company_name = body.company_name.strip()
    else:
        db.add(TenantSettings(id=1, company_name=body.company_name.strip()))

    # Общий чат организации: то же имя, что у группы/компании (видно в списке чатов)
    company = body.company_name.strip()
    room = ChatRoom(name=company, type="group", created_by=user.id)
    db.add(room)
    await db.flush()
    db.add(ChatRoomMember(room_id=room.id, user_id=user.id))
    db.add(
        ChatMessage(
            room_id=room.id,
            sender_id=user.id,
            content=f"Общий чат организации «{company}». Добро пожаловать!",
        )
    )

    await db.commit()
    await db.refresh(link)

    base = _join_base_url()
    if base:
        join_url = f"{base}/join/{link.token}"
    else:
        # Фронт подставит origin; отдаём относительный путь
        join_url = f"/join/{link.token}"

    return InviteLinkOut(
        id=link.id,
        token=link.token,
        company_name=link.company_name,
        is_permanent=link.is_permanent,
        expires_at=link.expires_at,
        max_visits=link.max_visits,
        join_url=join_url,
    )
