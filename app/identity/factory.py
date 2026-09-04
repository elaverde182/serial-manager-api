"""Selección del proveedor de identidad según AUTH_PROVIDER (un solo punto de cambio)."""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.identity.base import IdentityProvider


@lru_cache
def get_identity_provider() -> IdentityProvider:
    provider = settings.auth_provider.lower()
    if provider == "local":
        from app.identity.local_provider import LocalProvider

        return LocalProvider()
    if provider == "oidc":
        from app.identity.oidc_provider import OIDCProvider

        return OIDCProvider()
    if provider == "ldap":
        from app.identity.ldap_provider import LDAPProvider

        return LDAPProvider()
    if provider == "external_api":
        from app.identity.external_api_provider import ExternalApiProvider

        return ExternalApiProvider()
    raise ValueError(f"AUTH_PROVIDER desconocido: {settings.auth_provider}")
