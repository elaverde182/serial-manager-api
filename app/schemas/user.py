"""Schemas de usuarios y roles."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None


class UserBase(BaseModel):
    username: str
    email: EmailStr | None = None
    full_name: str | None = None


class UserCreate(UserBase):
    password: str
    role_name: str = "operator"  # admin | operator
    default_country_code: str | None = None


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    full_name: str | None = None
    password: str | None = None
    role_name: str | None = None
    is_active: bool | None = None
    default_country_code: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str | None = None
    full_name: str | None = None
    role: RoleOut
    provider: str
    is_active: bool
    default_country_code: str | None = None
    last_login_at: datetime | None = None
    created_at: datetime
