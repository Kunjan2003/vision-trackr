from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

def utcnow():
    return datetime.now(timezone.utc)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    department: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class WorkSession(Base):
    __tablename__ = "work_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_tick_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="working")
    state_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, default=utcnow)
    user: Mapped[User] = relationship()

class ActivitySlice(Base):
    __tablename__ = "activity_slices"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("work_sessions.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(24))
    app_name: Mapped[str] = mapped_column(String(255), default="")
    window_title: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(24), default="neutral")

class CategoryRule(Base):
    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "pattern"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pattern: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(24))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class UserSettings(Base):
    __tablename__ = "user_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    idle_threshold: Mapped[int] = mapped_column(Integer, default=300)
    poll_interval: Mapped[int] = mapped_column(Integer, default=4)
    auto_start: Mapped[bool] = mapped_column(Boolean, default=True)
    break_reminder_minutes: Mapped[int] = mapped_column(Integer, default=60)
    daily_goal_minutes: Mapped[int] = mapped_column(Integer, default=480)
    theme: Mapped[str] = mapped_column(String(10), default="dark")
