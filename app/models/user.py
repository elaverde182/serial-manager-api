"""Modelos de usuarios y roles (RBAC)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(160))

    users: Mapped[list[User]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_user_provider_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(160))
    full_name: Mapped[str | None] = mapped_column(String(160))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), default="local", nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(160))
    default_country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("countries.code")
    )
    language: Mapped[str | None] = mapped_column(String(5))  # 'es' | 'en'; null = autodetectar
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    role: Mapped[Role] = relationship(back_populates="users")
