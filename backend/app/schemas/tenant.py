from datetime import datetime

from pydantic import BaseModel, Field


class CompanyProfileOut(BaseModel):
    company_name: str


class InviteLinkCreate(BaseModel):
    company_name: str = Field(..., min_length=1, max_length=255)
    is_permanent: bool = False
    """Если временная ссылка — срок действия в часах (1–8760)."""
    duration_hours: int | None = Field(None, ge=1, le=8760)
    """Максимум переходов; None = без ограничения."""
    max_visits: int | None = Field(None, ge=1)


class InviteLinkOut(BaseModel):
    id: int
    token: str
    company_name: str
    is_permanent: bool
    expires_at: datetime | None
    max_visits: int | None
    join_url: str

    model_config = {"from_attributes": True}
