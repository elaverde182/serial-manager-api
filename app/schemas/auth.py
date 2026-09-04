"""Schemas de autenticación."""
from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int | None = None
    username: str
    role: str
    provider: str
    full_name: str | None = None
    email: str | None = None
    default_country_code: str | None = None
    language: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo


class RefreshRequest(BaseModel):
    refresh_token: str


class MeUpdate(BaseModel):
    """Campos editables vía PATCH /auth/me. `language` es autoservicio;
    `default_country_code` solo lo puede cambiar un administrador."""

    default_country_code: str | None = None
    language: str | None = None
