"""Proveedor por API externa: el cliente expone su microservicio de usuarios.

Valida credenciales llamando al endpoint del cliente y, si es válido, emitimos
nuestro JWT (mismo formato que en local). El rol se lee del campo configurado.
"""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.identity.base import IdentityProvider, Principal


class ExternalApiProvider(IdentityProvider):
    name = "external_api"

    def authenticate(
        self, db: Session, username: str, password: str
    ) -> Principal | None:
        if not settings.extauth_validate_url:
            raise NotImplementedError(
                "ExternalApiProvider requiere EXTAUTH_VALIDATE_URL configurada."
            )
        headers = {}
        if settings.extauth_api_key:
            headers["Authorization"] = f"Bearer {settings.extauth_api_key}"
        try:
            resp = httpx.post(
                settings.extauth_validate_url,
                json={"username": username, "password": password},
                headers=headers,
                timeout=10,
            )
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        data = resp.json()
        role_value = str(data.get(settings.extauth_role_field, "operator")).lower()
        role = "admin" if "admin" in role_value else "operator"
        return Principal(
            subject=str(data.get("id", username)),
            username=username,
            role=role,
            provider=self.name,
            email=data.get("email"),
            full_name=data.get("full_name") or data.get("name"),
            raw_claims=data,
        )

    def verify_token(self, token: str) -> Principal | None:
        from app.identity.local_provider import LocalProvider

        principal = LocalProvider().verify_token(token)
        if principal:
            principal.provider = self.name
        return principal
