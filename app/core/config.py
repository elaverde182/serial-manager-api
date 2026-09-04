"""Configuración de la aplicación (Pydantic Settings, leída desde .env)."""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "Serial Manager"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Base de datos
    database_url: str = "sqlite:///./serial_manager.db"

    # Auth / JWT
    auth_provider: str = "local"  # local | oidc | ldap | external_api
    jwt_secret: str = "cambia-esto-en-produccion"
    jwt_alg: str = "HS256"
    jwt_expires_min: int = 60
    jwt_refresh_expires_min: int = 10080  # 7 días
    login_max_attempts: int = 20
    login_window_s: int = 60

    # Admin inicial (seed)
    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_fullname: str = "Administrador"

    # OIDC
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_role_claim: str = "realm_access.roles"

    # LDAP
    ldap_url: str = ""
    ldap_base_dn: str = ""
    ldap_bind_template: str = ""
    ldap_admin_group: str = ""

    # API externa de usuarios
    extauth_validate_url: str = ""
    extauth_api_key: str = ""
    extauth_role_field: str = "role"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
