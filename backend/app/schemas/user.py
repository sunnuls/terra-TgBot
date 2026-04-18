from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class UserOut(BaseModel):
    id: int
    full_name: str | None
    username: str | None
    phone: str | None
    tz: str
    is_active: bool
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    tz: str | None = None


class UserAdminUpdate(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    full_name: str | None = None


class UserListItem(BaseModel):
    id: int
    full_name: str | None
    username: str | None
    phone: str | None
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
