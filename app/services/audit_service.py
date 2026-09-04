"""Servicio de auditoría: registra acciones sensibles."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.identity.base import Principal
from app.models.audit import AuditLog


def record(
    db: Session,
    action: str,
    *,
    principal: Principal | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    meta: dict | None = None,
    ip_address: str | None = None,
    commit: bool = True,
) -> AuditLog:
    log = AuditLog(
        actor_id=principal.user_id if principal else None,
        actor_label=principal.username if principal else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        meta=meta,
        ip_address=ip_address,
    )
    db.add(log)
    if commit:
        db.commit()
    return log
