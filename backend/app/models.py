import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str]
    display_name: Mapped[str] = mapped_column(default="")
    mfa_enabled: Mapped[bool] = mapped_column(default=False)
    mfa_secret: Mapped[str | None] = mapped_column(default=None)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_locked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    preferences: Mapped["UserPreference | None"] = relationship(back_populates="user", cascade="all, delete-orphan", uselist=False)
    jobs: Mapped[list["JobApplication"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    dark_mode: Mapped[bool] = mapped_column(default=True)
    default_view: Mapped[str] = mapped_column(default="kanban")
    interview_rounds: Mapped[int] = mapped_column(default=3)
    user: Mapped[User] = relationship(back_populates="preferences")


class JobApplication(Base):
    __tablename__ = "job_applications"
    __table_args__ = (Index("ix_job_applications_user_id_status", "user_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(default="")
    skills: Mapped[str] = mapped_column(default="")
    pay: Mapped[str] = mapped_column(default="")
    location: Mapped[str] = mapped_column(default="")
    nickname: Mapped[str] = mapped_column(default="")
    source_url: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(String(30), default="Applied")
    interview_round: Mapped[int | None] = mapped_column(default=None)
    status_events: Mapped[list] = mapped_column(JSON, default=list)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(back_populates="jobs")


class LoginEvent(Base):
    __tablename__ = "login_events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, default=None)
    username: Mapped[str] = mapped_column(String(320))
    mfa_enabled: Mapped[bool] = mapped_column(default=False)
    ip_address: Mapped[str] = mapped_column(String(64))
    succeeded: Mapped[bool] = mapped_column(default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    latitude: Mapped[float | None] = mapped_column(default=None)
    longitude: Mapped[float | None] = mapped_column(default=None)
    city: Mapped[str | None] = mapped_column(default=None)
    country: Mapped[str | None] = mapped_column(default=None)
