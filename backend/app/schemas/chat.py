from datetime import datetime
from pydantic import BaseModel


class ChatRoomCreate(BaseModel):
    name: str
    type: str = "group"  # "dm" or "group"
    member_ids: list[int] = []


class ChatRoomUpdate(BaseModel):
    name: str


class ChatRoomOut(BaseModel):
    id: int
    name: str | None
    type: str
    created_by: int | None
    created_at: datetime
    member_count: int = 0
    last_message: str | None = None
    is_reports_feed: bool = False

    model_config = {"from_attributes": True}


class ChatRoomMemberOut(BaseModel):
    user_id: int
    full_name: str | None = None
    username: str | None = None


class ChatAddMembersBody(BaseModel):
    user_ids: list[int]


class ChatMessageCreate(BaseModel):
    content: str


class ChatMessageOut(BaseModel):
    id: int
    room_id: int
    sender_id: int | None
    sender_name: str | None = None
    content: str
    created_at: datetime
    is_deleted: bool

    model_config = {"from_attributes": True}


class WSMessage(BaseModel):
    type: str  # "message", "typing", "read"
    content: str | None = None
    message_id: int | None = None
