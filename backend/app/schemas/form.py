from datetime import datetime
from pydantic import BaseModel
from pydantic import ConfigDict
from typing import Any


class FormFieldSchema(BaseModel):
    id: str
    type: str  # date, number, text, select_one, select_many, table
    label: str
    required: bool = False
    source: str | None = None  # activities, locations, crops, etc.
    options: list[str] | None = None
    min: float | None = None
    max: float | None = None
    placeholder: str | None = None
    columns: list[str] | None = None  # for table type


class FormSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    fields: list[FormFieldSchema] = []


class FormTemplateCreate(BaseModel):
    name: str
    title: str
    schema: FormSchema
    roles: list[str] = []
    group_ids: list[int] = []


class FormTemplateUpdate(BaseModel):
    title: str | None = None
    schema: FormSchema | None = None
    is_active: bool | None = None
    roles: list[str] | None = None
    group_ids: list[int] | None = None


class FormTemplateOut(BaseModel):
    id: int
    name: str
    title: str
    schema: dict
    is_active: bool
    created_by: int | None
    created_at: datetime
    roles: list[str]

    model_config = {"from_attributes": True}
