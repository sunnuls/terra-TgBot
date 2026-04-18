from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from app.core.database import get_db, AsyncSessionLocal
from app.core.redis import get_redis
from app.models.chat import ChatRoom, ChatRoomMember, ChatMessage
from app.models.user import User
from app.models.tenant import TenantSettings
from app.schemas.chat import (
    ChatAddMembersBody,
    ChatRoomCreate,
    ChatRoomUpdate,
    ChatRoomMemberOut,
    ChatRoomOut,
    ChatMessageOut,
    WSMessage,
)
from app.api.deps import get_current_user, ws_get_current_user, require_admin
from app.realtime.chat_hub import connections as _connections, broadcast_chat_message, push_offline_room_members
import json
from datetime import datetime, timezone

router = APIRouter(prefix="/chat", tags=["chat"])


async def _reports_feed_room_id(db: AsyncSession) -> int | None:
    ts = (await db.execute(select(TenantSettings).where(TenantSettings.id == 1))).scalar_one_or_none()
    return ts.reports_feed_room_id if ts else None


@router.get("/feed-room", response_model=ChatRoomOut | None)
async def get_feed_room(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт (если нужно) и возвращает комнату «Отчётность».
    Автоматически добавляет текущего пользователя в участники."""
    from app.services.reports_feed_chat import get_or_create_reports_feed_room
    room_id = await get_or_create_reports_feed_room(db)
    if not room_id:
        return None
    # Убедиться что текущий пользователь — участник
    member_check = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == current_user.id
        )
    )
    if not member_check.scalar_one_or_none():
        db.add(ChatRoomMember(room_id=room_id, user_id=current_user.id))
        await db.commit()
    room_result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = room_result.scalar_one_or_none()
    return await _room_out(db, room) if room else None


@router.get("/rooms", response_model=list[ChatRoomOut])
async def list_rooms(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatRoom).join(ChatRoomMember, ChatRoomMember.room_id == ChatRoom.id).where(
            ChatRoomMember.user_id == current_user.id
        ).order_by(ChatRoom.created_at.desc())
    )
    rooms = result.scalars().all()
    feed_rid = await _reports_feed_room_id(db)
    out = []
    for room in rooms:
        member_count_result = await db.execute(
            select(ChatRoomMember).where(ChatRoomMember.room_id == room.id)
        )
        members = member_count_result.scalars().all()

        last_msg_result = await db.execute(
            select(ChatMessage).where(
                ChatMessage.room_id == room.id,
                ChatMessage.is_deleted == False
            ).order_by(ChatMessage.created_at.desc()).limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()

        out.append(ChatRoomOut(
            id=room.id,
            name=room.name,
            type=room.type,
            created_by=room.created_by,
            created_at=room.created_at,
            member_count=len(members),
            last_message=last_msg.content if last_msg else None,
            is_reports_feed=feed_rid is not None and room.id == feed_rid,
        ))
    return out


async def _room_out(db: AsyncSession, room: ChatRoom, feed_room_id: int | None = None) -> ChatRoomOut:
    member_count_result = await db.execute(
        select(ChatRoomMember).where(ChatRoomMember.room_id == room.id)
    )
    members = member_count_result.scalars().all()
    last_msg_result = await db.execute(
        select(ChatMessage).where(
            ChatMessage.room_id == room.id,
            ChatMessage.is_deleted == False,
        ).order_by(ChatMessage.created_at.desc()).limit(1)
    )
    last_msg = last_msg_result.scalar_one_or_none()
    if feed_room_id is None:
        feed_room_id = await _reports_feed_room_id(db)
    is_feed = feed_room_id is not None and room.id == feed_room_id
    return ChatRoomOut(
        id=room.id,
        name=room.name,
        type=room.type,
        created_by=room.created_by,
        created_at=room.created_at,
        member_count=len(members),
        last_message=last_msg.content if last_msg else None,
        is_reports_feed=is_feed,
    )


@router.patch("/rooms/{room_id}", response_model=ChatRoomOut)
async def update_room(
    room_id: int,
    body: ChatRoomUpdate,
    db: AsyncSession = Depends(get_db),
    _auth: tuple = Depends(require_admin),
):
    feed_rid = await _reports_feed_room_id(db)
    if feed_rid is not None and room_id == feed_rid:
        raise HTTPException(400, "Комната ленты отчётов не настраивается")
    room_result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    if room.type != "group":
        raise HTTPException(400, "Можно переименовать только групповые чаты")
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Название не может быть пустым")
    room.name = name
    await db.commit()
    await db.refresh(room)
    return await _room_out(db, room, feed_room_id=feed_rid)


@router.get("/rooms/{room_id}/members", response_model=list[ChatRoomMemberOut])
async def list_room_members(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_check = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == current_user.id
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(403, "Not a member")

    q = (
        select(ChatRoomMember.user_id, User.full_name, User.username)
        .join(User, User.id == ChatRoomMember.user_id)
        .where(ChatRoomMember.room_id == room_id)
        .order_by(User.id)
    )
    result = await db.execute(q)
    return [
        ChatRoomMemberOut(user_id=row[0], full_name=row[1], username=row[2]) for row in result.all()
    ]


@router.post("/rooms/{room_id}/members", response_model=ChatRoomOut)
async def add_room_members(
    room_id: int,
    body: ChatAddMembersBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_check = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == current_user.id
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(403, "Not a member")

    room_result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    if room.type != "group":
        raise HTTPException(400, "Можно добавлять участников только в групповые чаты")

    if not body.user_ids:
        return await _room_out(db, room)

    existing = await db.execute(
        select(ChatRoomMember.user_id).where(ChatRoomMember.room_id == room_id)
    )
    existing_ids = {r[0] for r in existing.all()}

    users_result = await db.execute(
        select(User).where(User.id.in_(body.user_ids), User.is_active == True)
    )
    found_users = {u.id: u for u in users_result.scalars().all()}

    added = 0
    for uid in body.user_ids:
        if uid in existing_ids:
            continue
        if uid not in found_users:
            continue
        db.add(ChatRoomMember(room_id=room_id, user_id=uid))
        existing_ids.add(uid)
        added += 1

    if added:
        await db.commit()
        await db.refresh(room)

    return await _room_out(db, room)


@router.delete("/rooms/{room_id}/members/{user_id}", status_code=204)
async def remove_room_member(
    room_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _auth: tuple = Depends(require_admin),
):
    """Удалить участника из группы (только администратор). В группе должен остаться минимум один участник."""
    room_result = await db.execute(select(ChatRoom).where(ChatRoom.id == room_id))
    room = room_result.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Room not found")
    if room.type != "group":
        raise HTTPException(400, "Только для групповых чатов")

    members = (
        await db.execute(select(ChatRoomMember).where(ChatRoomMember.room_id == room_id))
    ).scalars().all()
    if len(members) <= 1:
        raise HTTPException(400, "В группе должен остаться хотя бы один участник")

    mem_result = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id,
            ChatRoomMember.user_id == user_id,
        )
    )
    mem = mem_result.scalar_one_or_none()
    if not mem:
        raise HTTPException(404, "Участник не найден в чате")

    await db.delete(mem)
    await db.commit()
    return Response(status_code=204)


@router.post("/rooms", response_model=ChatRoomOut, status_code=201)
async def create_room(
    body: ChatRoomCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.type == "dm":
        if len(body.member_ids) != 1:
            raise HTTPException(400, "DM requires exactly 1 other member")
        other_id = body.member_ids[0]
        # Check existing DM
        existing = await db.execute(
            select(ChatRoom).join(ChatRoomMember, ChatRoomMember.room_id == ChatRoom.id).where(
                ChatRoom.type == "dm",
                ChatRoomMember.user_id == current_user.id
            )
        )
        for room in existing.scalars().all():
            other_check = await db.execute(
                select(ChatRoomMember).where(
                    ChatRoomMember.room_id == room.id,
                    ChatRoomMember.user_id == other_id
                )
            )
            if other_check.scalar_one_or_none():
                member_count = (await db.execute(
                    select(ChatRoomMember).where(ChatRoomMember.room_id == room.id)
                )).scalars().all()
                return ChatRoomOut(
                    id=room.id, name=room.name, type=room.type,
                    created_by=room.created_by, created_at=room.created_at,
                    member_count=len(member_count),
                    is_reports_feed=False,
                )

    room = ChatRoom(name=body.name, type=body.type, created_by=current_user.id)
    db.add(room)
    await db.flush()

    member_ids = list(set([current_user.id] + body.member_ids))
    for uid in member_ids:
        db.add(ChatRoomMember(room_id=room.id, user_id=uid))

    await db.commit()
    await db.refresh(room)
    return ChatRoomOut(
        id=room.id, name=room.name, type=room.type,
        created_by=room.created_by, created_at=room.created_at,
        member_count=len(member_ids),
        is_reports_feed=False,
    )


@router.get("/rooms/{room_id}/messages", response_model=list[ChatMessageOut])
async def get_messages(
    room_id: int,
    before: int | None = None,
    limit: int = Query(50, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    member_check = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == current_user.id
        )
    )
    if not member_check.scalar_one_or_none():
        raise HTTPException(403, "Not a member")

    q = select(ChatMessage, User).join(User, ChatMessage.sender_id == User.id, isouter=True).where(
        ChatMessage.room_id == room_id, ChatMessage.is_deleted == False
    )
    if before:
        q = q.where(ChatMessage.id < before)
    q = q.order_by(ChatMessage.id.desc()).limit(limit)

    result = await db.execute(q)
    msgs = []
    for msg, user in result.all():
        msgs.append(ChatMessageOut(
            id=msg.id, room_id=msg.room_id, sender_id=msg.sender_id,
            sender_name=user.full_name if user else None,
            content=msg.content, created_at=msg.created_at, is_deleted=msg.is_deleted
        ))
    return list(reversed(msgs))


@router.websocket("/ws/{room_id}")
async def ws_chat(
    websocket: WebSocket,
    room_id: int,
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await ws_get_current_user(websocket, db)
    except Exception:
        return

    member_check = await db.execute(
        select(ChatRoomMember).where(
            ChatRoomMember.room_id == room_id, ChatRoomMember.user_id == user.id
        )
    )
    if not member_check.scalar_one_or_none():
        await websocket.close(code=4003)
        return

    await websocket.accept()
    feed_rid = await _reports_feed_room_id(db)
    if room_id not in _connections:
        _connections[room_id] = {}
    _connections[room_id][user.id] = websocket

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            ws_msg = WSMessage(**data)

            if ws_msg.type == "message" and ws_msg.content:
                if feed_rid is not None and room_id == feed_rid:
                    await websocket.send_json({
                        "type": "error",
                        "detail": "В ленте отчётов только просмотр — отправка отключена",
                    })
                    continue
                async with AsyncSessionLocal() as save_db:
                    msg = ChatMessage(room_id=room_id, sender_id=user.id, content=ws_msg.content)
                    save_db.add(msg)
                    await save_db.commit()
                    await save_db.refresh(msg)

                    await broadcast_chat_message(room_id, msg, user.full_name)
                    await push_offline_room_members(
                        room_id,
                        user.id,
                        user.full_name or "TerraApp",
                        ws_msg.content or "",
                        save_db,
                    )

    except WebSocketDisconnect:
        pass
    finally:
        _connections.get(room_id, {}).pop(user.id, None)
