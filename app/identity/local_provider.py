"""Proveedor de identidad LOCAL: usuarios en nuestra BD (desarrollo / standalone)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.identity.base import IdentityProvider, Principal
from app.models.user import User


class LocalProvider(IdentityProvider):
    name = "local"

    def authenticate(
        self, db: Session, username: str, password: str
    ) -> Principal | None:
        user = db.execute(
            select(User).where(User.username == username, User.is_active.is_(True))
        ).scalar_one_or_none()
        if not user or not security.verify_password(password, user.password_hash):
            return None
        return self._to_principal(user)

    def verify_token(self, token: str) -> Principal | None:
        claims = security.decode_token(token)
        if not claims or claims.get("type") != "access":
            return None
        return Principal(
            subject=str(claims.get("sub")),
            username=claims.get("username", ""),
            role=claims.get("role", "operator"),
            provider=self.name,
            user_id=int(claims["sub"]) if str(claims.get("sub", "")).isdigit() else None,
            email=claims.get("email"),
            full_name=claims.get("full_name"),
            raw_claims=claims,
        )

    @staticmethod
    def _to_principal(user: User) -> Principal:
        return Principal(
            subject=str(user.id),
            username=user.username,
            role=user.role.name,
            provider="local",
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
        )
