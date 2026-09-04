"""Servicio del ciclo de vida del equipo (estados + historial)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.equipment import EquipmentStatusHistory, EquipmentTag


def add_history(
    db: Session,
    tag: EquipmentTag,
    *,
    event: str,
    from_status: str | None,
    to_status: str | None,
    reason: str | None,
    changed_by: int | None,
    commit: bool = True,
) -> EquipmentStatusHistory:
    h = EquipmentStatusHistory(
        equipment_id=tag.id,
        event=event,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
        changed_by=changed_by,
    )
    db.add(h)
    if commit:
        db.commit()
    return h


def discard(
    db: Session, tag: EquipmentTag, *, reason: str, changed_by: int | None
) -> EquipmentTag:
    if tag.status == "discarded":
        raise ValueError("El equipo ya está descartado")
    prev = tag.status
    tag.status = "discarded"
    tag.reason = reason
    add_history(
        db,
        tag,
        event="discarded",
        from_status=prev,
        to_status="discarded",
        reason=reason,
        changed_by=changed_by,
        commit=False,
    )
    db.commit()
    db.refresh(tag)
    return tag


def inbound(
    db: Session, tag: EquipmentTag, *, notes: str | None, changed_by: int | None
) -> EquipmentTag:
    add_history(
        db,
        tag,
        event="inbound",
        from_status=tag.status,
        to_status=tag.status,
        reason=notes,
        changed_by=changed_by,
        commit=False,
    )
    db.commit()
    db.refresh(tag)
    return tag
