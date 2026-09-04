"""Endpoints de autenticación."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.identity.base import Principal
from app.identity.factory import get_identity_provider
from app.models.catalog import Country
from app.models.user import User
from app.schemas.auth import LoginRequest, MeUpdate, RefreshRequest, TokenResponse, UserInfo
from app.services import audit_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _local_prefs(db: Session, principal: Principal) -> tuple[str | None, str | None]:
    """(default_country_code, language) guardados localmente para este usuario, si aplica."""
    if not principal.user_id:
        return None, None
    user = db.get(User, principal.user_id)
    if not user:
        return None, None
    return user.default_country_code, user.language


def _issue_tokens(principal: Principal, db: Session) -> TokenResponse:
    claims = {
        "sub": principal.subject,
        "username": principal.username,
        "role": principal.role,
        "provider": principal.provider,
        "full_name": principal.full_name,
        "email": principal.email,
    }
    country, language = _local_prefs(db, principal)
    return TokenResponse(
        access_token=security.create_access_token(claims),
        refresh_token=security.create_refresh_token(claims),
        expires_in=settings.jwt_expires_min * 60,
        user=UserInfo(
            id=principal.user_id,
            username=principal.username,
            role=principal.role,
            provider=principal.provider,
            full_name=principal.full_name,
            email=principal.email,
            default_country_code=country,
            language=language,
        ),
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    provider = get_identity_provider()
    if not provider.supports_password_login():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El proveedor '{provider.name}' no usa login por contraseña; "
                "autentíquese contra el IdP del cliente."
            ),
        )
    principal = provider.authenticate(db, payload.username, payload.password)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas"
        )

    # Actualiza last_login en modo local.
    if principal.user_id:
        user = db.get(User, principal.user_id)
        if user:
            user.last_login_at = datetime.now(tz=timezone.utc)
            db.commit()

    audit_service.record(
        db, "login", principal=principal, ip_address=request.client.host if request.client else None
    )
    return _issue_tokens(principal, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    claims = security.decode_token(payload.refresh_token)
    if not claims or claims.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido"
        )
    principal = Principal(
        subject=str(claims.get("sub")),
        username=claims.get("username", ""),
        role=claims.get("role", "operator"),
        provider=claims.get("provider", settings.auth_provider),
        user_id=int(claims["sub"]) if str(claims.get("sub", "")).isdigit() else None,
        email=claims.get("email"),
        full_name=claims.get("full_name"),
    )
    return _issue_tokens(principal, db)


@router.post("/logout")
def logout(principal: Principal = Depends(security.get_current_principal)):
    # Stateless JWT: el logout efectivo lo hace el cliente descartando el token.
    # (Para invalidación server-side se añadiría una denylist de refresh tokens.)
    return {"detail": "Sesión cerrada"}


@router.get("/me", response_model=UserInfo)
def me(
    principal: Principal = Depends(security.get_current_principal),
    db: Session = Depends(get_db),
):
    country, language = _local_prefs(db, principal)
    return UserInfo(
        id=principal.user_id,
        username=principal.username,
        role=principal.role,
        provider=principal.provider,
        full_name=principal.full_name,
        email=principal.email,
        default_country_code=country,
        language=language,
    )


@router.patch("/me", response_model=UserInfo)
def update_me(
    payload: MeUpdate,
    principal: Principal = Depends(security.get_current_principal),
    db: Session = Depends(get_db),
):
    """Autoservicio parcial: el usuario puede cambiar su idioma, pero el país
    por defecto solo lo asigna un administrador (aquí si es admin, o vía /users)."""
    if not principal.user_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Este proveedor de identidad no permite editar preferencias locales",
        )
    user = db.get(User, principal.user_id)
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    dirty = False
    if payload.default_country_code is not None:
        if principal.role != "admin":
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Solo un administrador puede asignar el país por defecto",
            )
        code = payload.default_country_code or None
        if code and not db.get(Country, code):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"País inexistente: {code}")
        user.default_country_code = code
        dirty = True
    if payload.language is not None:
        lang = payload.language or None
        if lang and lang not in ("es", "en"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Idioma inválido: {lang}")
        user.language = lang
        dirty = True
    if dirty:
        db.commit()
        db.refresh(user)
    return UserInfo(
        id=user.id,
        username=user.username,
        role=principal.role,
        provider=user.provider,
        full_name=user.full_name,
        email=user.email,
        default_country_code=user.default_country_code,
        language=user.language,
    )
