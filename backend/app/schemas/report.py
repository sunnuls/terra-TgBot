from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    work_date: date
    hours: float = Field(..., ge=0.5, le=24)
    location: str
    location_grp: str
    activity: str
    activity_grp: str
    machine_type: str | None = None
    machine_name: str | None = None
    crop: str | None = None
    trips: int | None = None


class ReportUpdate(BaseModel):
    work_date: date | None = None
    hours: float | None = Field(None, ge=0.5, le=24)
    location: str | None = None
    location_grp: str | None = None
    activity: str | None = None
    activity_grp: str | None = None
    machine_type: str | None = None
    machine_name: str | None = None
    crop: str | None = None
    trips: int | None = None


class ReportOut(BaseModel):
    id: int
    created_at: datetime
    user_id: int | None
    reg_name: str | None
    work_date: date | None
    hours: float | None
    location: str | None
    location_grp: str | None
    activity: str | None
    activity_grp: str | None
    machine_type: str | None
    machine_name: str | None
    crop: str | None
    trips: int | None

    model_config = {"from_attributes": True}


class BrigReportCreate(BaseModel):
    work_date: date
    work_type: str
    field: str
    shift: str
    rows: int = Field(..., ge=0)
    bags: int = Field(..., ge=0)
    workers: int = Field(..., ge=1)


class BrigReportUpdate(BaseModel):
    work_date: date | None = None
    work_type: str | None = None
    field: str | None = None
    shift: str | None = None
    rows: int | None = Field(None, ge=0)
    bags: int | None = Field(None, ge=0)
    workers: int | None = Field(None, ge=1)


class BrigReportOut(BaseModel):
    id: int
    created_at: datetime
    user_id: int | None
    username: str | None
    work_date: date | None
    work_type: str | None
    field: str | None
    shift: str | None
    rows: int | None
    bags: int | None
    workers: int | None

    model_config = {"from_attributes": True}


class FormResponseCreate(BaseModel):
    form_id: int
    data: dict


class FormResponseOut(BaseModel):
    id: int
    form_id: int
    user_id: int
    data: dict
    submitted_at: datetime

    model_config = {"from_attributes": True}


class StatsOut(BaseModel):
    period: str
    total_hours: float
    report_count: int
    days_worked: int


class ReportFeedItemOut(BaseModel):
    """ОТД: классическая запись в reports или ответ flow-формы «otd» (form_responses)."""

    source: Literal["otd", "form"]
    id: int
    created_at: datetime
    user_id: int | None = None
    reg_name: str | None = None
    work_date: date | None = None
    hours: float | None = None
    location: str | None = None
    location_grp: str | None = None
    activity: str | None = None
    activity_grp: str | None = None
    machine_type: str | None = None
    machine_name: str | None = None
    crop: str | None = None
    trips: int | None = None
    form_title: str | None = None
