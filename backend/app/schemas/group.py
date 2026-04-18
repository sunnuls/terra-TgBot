from datetime import datetime
from pydantic import BaseModel


class GroupCreate(BaseModel):
    name: str
    parent_id: int | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    parent_id: int | None = None


class GroupOut(BaseModel):
    id: int
    name: str
    parent_id: int | None
    created_by: int | None
    created_at: datetime
    children: list["GroupOut"] = []
    member_count: int = 0

    model_config = {"from_attributes": True}


GroupOut.model_rebuild()


class GroupMemberAdd(BaseModel):
    user_id: int
    role: str | None = None


class GroupMemberOut(BaseModel):
    user_id: int
    group_id: int
    role: str | None
    full_name: str | None = None
    username: str | None = None

    model_config = {"from_attributes": True}
