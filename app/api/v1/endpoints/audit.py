"""Endpoints de auditoría y metadatos."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import __version__
from app.core import security
from app.core.config import settings
from app.core.database import get_db
from app.identity.base import Principal
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogOut

router = APIRouter(tags=["auditoría / meta"])


@router.get("/audit-logs", response_model=list[AuditLogOut])
def list_audit(
    actor: str | None = None,
    action: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: object = Depends(security.require_role("admin")),
):
    stmt = select(AuditLog)
    if actor:
        stmt = stmt.where(AuditLog.actor_label == actor)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    return db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).scalars().all()


@router.get("/meta/config")
def meta_config(_: Principal = Depends(security.get_current_principal)):
    return {
        "app": settings.app_name,
        "version": __version__,
        "auth_provider": settings.auth_provider,
        "supports_password_login": settings.auth_provider in {"local", "ldap", "external_api"},
        "default_serial_template": "{country}-{consecutive:06d}-{random}",
    }
