from sqlalchemy import BigInteger, Date, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reg_name: Mapped[str | None] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(String(255))
    location_grp: Mapped[str | None] = mapped_column(String(50))
    activity: Mapped[str | None] = mapped_column(String(255))
    activity_grp: Mapped[str | None] = mapped_column(String(50))
    work_date: Mapped[Date | None] = mapped_column(Date)
    hours: Mapped[float | None] = mapped_column(Float)
    machine_type: Mapped[str | None] = mapped_column(String(50))
    machine_name: Mapped[str | None] = mapped_column(String(255))
    crop: Mapped[str | None] = mapped_column(String(100))
    trips: Mapped[int | None] = mapped_column(Integer)


class BrigadierReport(Base):
    __tablename__ = "brigadier_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username: Mapped[str | None] = mapped_column(String(100))
    work_type: Mapped[str | None] = mapped_column(String(255))
    field: Mapped[str | None] = mapped_column(String(255))
    shift: Mapped[str | None] = mapped_column(String(50))
    rows: Mapped[int | None] = mapped_column(Integer)
    bags: Mapped[int | None] = mapped_column(Integer)
    workers: Mapped[int | None] = mapped_column(Integer)
    work_date: Mapped[Date | None] = mapped_column(Date)


class FormResponse(Base):
    __tablename__ = "form_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id: Mapped[int] = mapped_column(Integer, ForeignKey("form_templates.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"))
    data: Mapped[dict] = mapped_column(JSONB)
    submitted_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
