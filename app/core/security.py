"""Seguridad: hashing de contraseñas, emisión/validación de JWT y dependencias de auth."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.api_v1_prefix}/auth/login", auto_error=False
)


# ---------- Contraseñas (bcrypt directo, compatible con Python 3.13) ----------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------- JWT ----------
def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_access_token(claims: dict) -> str:
    payload = claims.copy()
    payload.update(
        {
            "type": "access",
            "iat": _now(),
            "exp": _now() + timedelta(minutes=settings.jwt_expires_min),
        }
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def create_refresh_token(claims: dict) -> str:
    payload = claims.copy()
    payload.update(
        {
            "type": "refresh",
            "iat": _now(),
            "exp": _now() + timedelta(minutes=settings.jwt_refresh_expires_min),
        }
    )
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        return None


# ---------- Dependencias de autenticación ----------
# (se importan aquí para evitar ciclos; el provider se resuelve por factory)
from app.identity.base import Principal  # noqa: E402
from app.identity.factory import get_identity_provider  # noqa: E402


def get_current_principal(token: str | None = Depends(oauth2_scheme)) -> Principal:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    provider = get_identity_provider()
    principal = provider.verify_token(token)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return principal


def require_role(*roles: str):
    def checker(principal: Principal = Depends(get_current_principal)) -> Principal:
        if roles and principal.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No autorizado para esta acción",
            )
        return principal

    return checker
