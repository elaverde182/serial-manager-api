"""Proveedor OIDC: el IdP del cliente (Keycloak/Azure AD/Auth0) emite el token; lo validamos por JWKS."""
from __future__ import annotations

import jwt
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.identity.base import IdentityProvider, Principal


class OIDCProvider(IdentityProvider):
    name = "oidc"

    def __init__(self) -> None:
        self._jwk_client: PyJWKClient | None = None
        if settings.oidc_jwks_url:
            self._jwk_client = PyJWKClient(settings.oidc_jwks_url)

    def supports_password_login(self) -> bool:
        # El login se hace contra el IdP del cliente; aquí solo validamos su token.
        return False

    def authenticate(
        self, db: Session, username: str, password: str
    ) -> Principal | None:
        # En OIDC el flujo de login lo realiza el front contra el IdP, no aquí.
        return None

    def verify_token(self, token: str) -> Principal | None:
        if not self._jwk_client:
            return None
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=settings.oidc_audience or None,
                issuer=settings.oidc_issuer or None,
                options={"verify_aud": bool(settings.oidc_audience)},
            )
        except jwt.PyJWTError:
            return None

        return Principal(
            subject=str(claims.get("sub")),
            username=claims.get("preferred_username") or claims.get("email", ""),
            role=self._map_role(claims),
            provider=self.name,
            email=claims.get("email"),
            full_name=claims.get("name"),
            raw_claims=claims,
        )

    @staticmethod
    def _map_role(claims: dict) -> str:
        """Lee el claim configurado (p. ej. realm_access.roles) y lo mapea a admin/operator."""
        path = settings.oidc_role_claim.split(".")
        node: object = claims
        for part in path:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
                break
        roles = node if isinstance(node, list) else [node] if node else []
        roles_lower = {str(r).lower() for r in roles}
        if any("admin" in r for r in roles_lower):
            return "admin"
        return "operator"
