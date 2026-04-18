"""Общий WebSocket-хаб для чатов: импортируется и из API, и из сервисов ленты отчётов."""

import json
from typing import TYPE_CHECKING

from fastapi import WebSocket
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatRoomMember, ChatMessage
from app.models.user import PushToken
from app.services.push import send_push_notifications

if TYPE_CHECKING:
    pass

# room_id -> { user_id -> WebSocket }
connections: dict[int, dict[int, WebSocket]] = {}


async def broadcast_chat_message(room_id: int, msg: ChatMessage, sender_name: str | None) -> None:
    broadcast = {
        "type": "message",
        "id": msg.id,
        "room_id": room_id,
        "sender_id": msg.sender_id,
        "sender_name": sender_name,
        "content": msg.content,
        "created_at": msg.created_at.isoformat(),
    }
    for _uid, ws in list(connections.get(room_id, {}).items()):
        try:
            await ws.send_text(json.dumps(broadcast))
        except Exception:
            pass


async def push_offline_room_members(
    room_id: int,
    sender_id: int,
    title: str,
    body: str,
    db: AsyncSession,
) -> None:
    members_result = await db.execute(
        select(ChatRoomMember.user_id).where(ChatRoomMember.room_id == room_id)
    )
    all_member_ids = [r[0] for r in members_result.all()]
    online_ids = set(connections.get(room_id, {}).keys())
    offline_ids = [uid for uid in all_member_ids if uid not in online_ids and uid != sender_id]
    if not offline_ids:
        return
    tokens_result = await db.execute(select(PushToken.token).where(PushToken.user_id.in_(offline_ids)))
    tokens = [r[0] for r in tokens_result.all()]
    if tokens:
        await send_push_notifications(
            tokens,
            title=title,
            body=body[:200],
            data={"room_id": room_id},
        )
