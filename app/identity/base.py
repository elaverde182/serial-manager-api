"""Contrato del proveedor de identidad conectable."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from sqlalchemy.orm import Session


@dataclass
class Principal:
    """Identidad normalizada, independiente del proveedor de origen."""

    subject: str  # id estable en el sistema origen
    username: str
    role: str  # 'admin' | 'operator' (ya mapeado)
    provider: str  # 'local' | 'oidc' | 'ldap' | 'external_api'
    user_id: int | None = None  # id en nuestra tabla users (FK), si aplica
    email: str | None = None
    full_name: str | None = None
    raw_claims: dict = field(default_factory=dict)


class IdentityProvider(ABC):
    """Toda autenticación de la app pasa por este contrato estable."""

    name: str = "base"

    @abstractmethod
    def authenticate(
        self, db: Session, username: str, password: str
    ) -> Principal | None:
        """Valida credenciales (flujo por contraseña). None si inválidas."""

    @abstractmethod
    def verify_token(self, token: str) -> Principal | None:
        """Valida un token ya emitido (propio o del IdP del cliente)."""

    def supports_password_login(self) -> bool:
        """True si acepta usuario/contraseña por /auth/login."""
        return True
