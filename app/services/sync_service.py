"""Servicio de sincronización offline/online (push idempotente + pull delta)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.equipment import EquipmentTag
from app.models.sync import SyncLog
from app.services import equipment_service, serial_service


def _already_processed(db: Session, client_op_id: str) -> SyncLog | None:
    return db.execute(
        select(SyncLog).where(SyncLog.client_op_id == client_op_id)
    ).scalar_one_or_none()


def _tag_dict(t: EquipmentTag) -> dict:
    """Serializa un equipo a un dict plano (mismo shape que el frontend espera)."""
    return {
        "id": t.id,
        "serial_code": t.serial_code,
        "country_code": t.country_code,
        "laboratory_id": t.laboratory_id,
        "consecutive": t.consecutive,
        "random_code": t.random_code,
        "equipment_type_id": t.equipment_type_id,
        "status": t.status,
        "reason": t.reason,
        "notes": t.notes,
        "created_by": t.created_by,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def push(
    db: Session,
    *,
    device_id: str,
    operations: list,
    created_by: int | None,
    role: str = "operator",
):
    applied: list[str] = []
    created: list[dict] = []
    conflicts: list[dict] = []
    rejected: list[dict] = []

    for op in operations:
        if _already_processed(db, op.client_op_id):
            applied.append(op.client_op_id)  # idempotente: ya aplicado antes
            continue

        try:
            status = "applied"
            detail = None
            created_tag: EquipmentTag | None = None
            if op.type == "create":
                p = op.payload
                # Misma regla que en los endpoints online: un no-admin solo
                # sincroniza seriales de su país asignado (SerialError → rejected).
                serial_service.check_country_allowed(
                    db, user_id=created_by, role=role, country_code=p["country_code"]
                )
                tag = serial_service.generate_tag(
                    db,
                    country_code=p["country_code"],
                    laboratory_id=p.get("laboratory_id"),
                    equipment_type_id=p.get("equipment_type_id"),
                    reason=p.get("reason"),
                    notes=p.get("notes"),
                    created_by=created_by,
                    client_op_id=op.client_op_id,
                    # Serial definitivo generado offline: se conserva (la etiqueta
                    # impresa sin conexión sigue siendo válida).
                    serial_code=p.get("serial_code"),
                )
                entity_id = tag.id
                created_tag = tag
            elif op.type == "discard":
                tag = db.get(EquipmentTag, op.entity_id)
                if not tag:
                    status, detail = "rejected", {"reason": "equipo no encontrado"}
                elif tag.status == "discarded":
                    status, detail = "rejected", {"reason": "already discarded"}
                else:
                    equipment_service.discard(
                        db, tag, reason=op.payload.get("reason", "otro"),
                        changed_by=created_by,
                    )
                entity_id = op.entity_id
            else:
                status, detail = "rejected", {"reason": f"operación no soportada: {op.type}"}
                entity_id = op.entity_id

            db.add(
                SyncLog(
                    client_op_id=op.client_op_id,
                    device_id=device_id,
                    operation=op.type,
                    entity_id=str(entity_id) if entity_id else None,
                    status=status,
                    conflict_detail=detail,
                )
            )
            db.commit()

            if status == "applied":
                applied.append(op.client_op_id)
                if created_tag is not None:
                    # Tras el commit los atributos se refrescan (created_at, etc.).
                    created.append(
                        {
                            "client_op_id": op.client_op_id,
                            "id": created_tag.id,
                            "serial_code": created_tag.serial_code,
                            "consecutive": created_tag.consecutive,
                            "country_code": created_tag.country_code,
                            "status": created_tag.status,
                        }
                    )
            elif status == "conflict":
                conflicts.append({"client_op_id": op.client_op_id, **(detail or {})})
            else:
                rejected.append(
                    {"client_op_id": op.client_op_id, "reason": (detail or {}).get("reason", "rechazado")}
                )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            rejected.append({"client_op_id": op.client_op_id, "reason": str(exc)})

    return applied, created, conflicts, rejected


def pull(db: Session, *, since: datetime | None):
    stmt = select(EquipmentTag)
    if since:
        stmt = stmt.where(EquipmentTag.updated_at > since)
    stmt = stmt.order_by(EquipmentTag.updated_at.asc()).limit(500)
    rows = db.execute(stmt).scalars().all()
    items = [_tag_dict(r) for r in rows]
    cursor = rows[-1].updated_at if rows else since
    return cursor, items
