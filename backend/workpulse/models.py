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
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("work_tasks.id"), nullable=True)

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

# WorkPulse v2: project accounting, privacy controls, focus, attendance and calendar.
from sqlalchemy import Text

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    client: Mapped[str] = mapped_column(String(120), default="")
    hourly_rate: Mapped[float] = mapped_column(Float, default=0.0)
    budget_hours: Mapped[float] = mapped_column(Float, default=0.0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("user_id", "name"),)

class WorkTask(Base):
    __tablename__ = "work_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(24), default="todo")
    estimate_minutes: Mapped[int] = mapped_column(Integer, default=0)

class ProjectRule(Base):
    __tablename__ = "project_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    pattern: Mapped[str] = mapped_column(String(160))
    __table_args__ = (UniqueConstraint("user_id", "pattern"),)

class ActiveAssignment(Base):
    __tablename__ = "active_assignment"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("work_tasks.id"), nullable=True)

class PrivacySettings(Base):
    __tablename__ = "privacy_settings"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    hide_window_titles: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    browser_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    meeting_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

class PrivacyRule(Base):
    __tablename__ = "privacy_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    pattern: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(12), default="exclude")
    __table_args__ = (UniqueConstraint("user_id", "pattern"),)

class ManualEntry(Base):
    __tablename__ = "manual_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("work_tasks.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(24), default="productive")
    note: Mapped[str] = mapped_column(String(300), default="")

class IdleReview(Base):
    __tablename__ = "idle_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    slice_id: Mapped[int] = mapped_column(ForeignKey("activity_slices.id"), unique=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

class FocusBlock(Base):
    __tablename__ = "focus_blocks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("work_tasks.id"), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=25)
    status: Mapped[str] = mapped_column(String(12), default="running")

class CalendarMeeting(Base):
    __tablename__ = "calendar_meetings"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    external_uid: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(180))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("user_id", "external_uid"),)
