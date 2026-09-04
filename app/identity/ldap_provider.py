"""Proveedor LDAP/Active Directory (stub estructurado).

Para activarlo en producción: añadir `ldap3` a las dependencias e implementar el
bind contra el directorio del cliente. La emisión del JWT propio se reutiliza de
`core.security` tras un bind exitoso, y el rol se mapea por pertenencia a grupo.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import settings
from app.identity.base import IdentityProvider, Principal


class LDAPProvider(IdentityProvider):
    name = "ldap"

    def authenticate(
        self, db: Session, username: str, password: str
    ) -> Principal | None:
        # TODO(producción): bind LDAP con ldap3 usando settings.ldap_*.
        #   conn = ldap3.Connection(settings.ldap_url,
        #       user=settings.ldap_bind_template.format(username=username),
        #       password=password, auto_bind=True)
        #   role = "admin" if en grupo settings.ldap_admin_group else "operator"
        raise NotImplementedError(
            "LDAPProvider requiere configuración LDAP y la dependencia 'ldap3'."
        )

    def verify_token(self, token: str) -> Principal | None:
        # Tras un bind exitoso emitimos JWT propio → se valida igual que en local.
        from app.identity.local_provider import LocalProvider

        principal = LocalProvider().verify_token(token)
        if principal:
            principal.provider = self.name
        return principal
