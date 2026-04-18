from sqlalchemy import Integer, String, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from typing import Optional
from app.core.database import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grp: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)   # "choices" | "message" | None
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    grp: Mapped[str] = mapped_column(String(50), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class MachineKind(Base):
    __tablename__ = "machine_kinds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)       # "Трактор", "КамАЗ"
    mode: Mapped[str] = mapped_column(String(20), default="list")          # "list" | "choices" | "message"
    pos: Mapped[int] = mapped_column(Integer, default=0)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)   # for mode="choices"
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # for mode="message"


class MachineItem(Base):
    __tablename__ = "machine_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind_id: Mapped[int] = mapped_column(Integer, ForeignKey("machine_kinds.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, default=0)


class Crop(Base):
    __tablename__ = "crops"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    pos: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CustomDict(Base):
    __tablename__ = "custom_dicts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)   # "Весовая", "Бригада"
    pos: Mapped[int] = mapped_column(Integer, default=0)


class CustomDictItem(Base):
    __tablename__ = "custom_dict_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dict_id: Mapped[int] = mapped_column(Integer, ForeignKey("custom_dicts.id", ondelete="CASCADE"))
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    options: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
