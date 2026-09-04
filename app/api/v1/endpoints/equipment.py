"""Endpoints de equipos (equipment_tags): generación, búsqueda, ciclo de vida e historial."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.identity.base import Principal
from app.models.equipment import EquipmentStatusHistory, EquipmentTag
from app.schemas.equipment import (
    DiscardRequest,
    HistoryOut,
    InboundRequest,
    PageMeta,
    TagBatchCreate,
    TagCreate,
    TagOut,
    TagPage,
    TagUpdate,
)
from app.services import audit_service, equipment_service, serial_service

router = APIRouter(prefix="/equipment-tags", tags=["equipos"])


def _enforce_country(db: Session, principal: Principal, country_code: str) -> None:
    """403 si un no-admin intenta generar seriales de un país distinto al asignado."""
    try:
        serial_service.check_country_allowed(
            db, user_id=principal.user_id, role=principal.role, country_code=country_code
        )
    except serial_service.SerialError as exc:
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))


@router.post("", response_model=TagOut, status_code=201)
def generate(
    payload: TagCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(security.require_role("operator", "admin")),
):
    _enforce_country(db, principal, payload.country_code)
    try:
        tag = serial_service.generate_tag(
            db,
            country_code=payload.country_code,
            laboratory_id=payload.laboratory_id,
            equipment_type_id=payload.equipment_type_id,
            reason=payload.reason,
            notes=payload.notes,
            created_by=principal.user_id,
            client_op_id=payload.client_op_id,
        )
    except serial_service.SerialError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    equipment_service.add_history(
        db, tag, event="created", from_status=None, to_status="active",
        reason=payload.reason, changed_by=principal.user_id, commit=False,
    )
    db.commit()
    db.refresh(tag)
    audit_service.record(
        db, "serial.generate", principal=principal, entity_type="equipment_tag",
        entity_id=tag.id, meta={"serial": tag.serial_code},
        ip_address=request.client.host if request.client else None,
    )
    return tag


@router.post("/batch", response_model=list[TagOut], status_code=201)
def generate_batch(
    payload: TagBatchCreate,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(security.require_role("operator", "admin")),
):
    """Genera `quantity` seriales de una sola vez (mismo país/lab/tipo de equipo),
    para etiquetar lotes de equipos iguales sin repetir el formulario uno por uno."""
    _enforce_country(db, principal, payload.country_code)
    tags: list[EquipmentTag] = []
    try:
        for _ in range(payload.quantity):
            tag = serial_service.generate_tag(
                db,
                country_code=payload.country_code,
                laboratory_id=payload.laboratory_id,
                equipment_type_id=payload.equipment_type_id,
                reason=payload.reason,
                notes=payload.notes,
                created_by=principal.user_id,
            )
            equipment_service.add_history(
                db, tag, event="created", from_status=None, to_status="active",
                reason=payload.reason, changed_by=principal.user_id, commit=False,
            )
            tags.append(tag)
    except serial_service.SerialError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    db.commit()
    for tag in tags:
        db.refresh(tag)
    audit_service.record(
        db, "serial.generate_batch", principal=principal, entity_type="equipment_tag",
        entity_id=None, meta={"count": len(tags), "country": payload.country_code},
        ip_address=request.client.host if request.client else None,
    )
    return tags


@router.get("", response_model=TagPage)
def list_tags(
    db: Session = Depends(get_db),
    _: Principal = Depends(security.get_current_principal),
    serial: str | None = None,
    country: str | None = None,
    laboratory_id: int | None = None,
    type_id: int | None = None,
    status_: str | None = Query(None, alias="status"),
    reason: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    stmt = select(EquipmentTag)
    if serial:
        stmt = stmt.where(EquipmentTag.serial_code == serial)
    if country:
        stmt = stmt.where(EquipmentTag.country_code == country)
    if laboratory_id is not None:
        stmt = stmt.where(EquipmentTag.laboratory_id == laboratory_id)
    if type_id is not None:
        stmt = stmt.where(EquipmentTag.equipment_type_id == type_id)
    if status_:
        stmt = stmt.where(EquipmentTag.status == status_)
    if reason:
        stmt = stmt.where(EquipmentTag.reason == reason)
    if date_from:
        stmt = stmt.where(EquipmentTag.created_at >= date_from)
    if date_to:
        stmt = stmt.where(EquipmentTag.created_at <= date_to)
    if q:
        stmt = stmt.where(EquipmentTag.serial_code.like(f"%{q}%"))

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = db.execute(
        stmt.order_by(EquipmentTag.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    ).scalars().all()
    return TagPage(items=rows, meta=PageMeta(page=page, size=size, total=total))


@router.get("/by-serial/{serial}", response_model=TagOut)
def get_by_serial(serial: str, db: Session = Depends(get_db), _: Principal = Depends(security.get_current_principal)):
    tag = db.execute(
        select(EquipmentTag).where(EquipmentTag.serial_code == serial)
    ).scalar_one_or_none()
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return tag


@router.get("/{tag_id}", response_model=TagOut)
def get_tag(tag_id: str, db: Session = Depends(get_db), _: Principal = Depends(security.get_current_principal)):
    tag = db.get(EquipmentTag, tag_id)
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return tag


@router.patch("/{tag_id}", response_model=TagOut)
def update_tag(
    tag_id: str,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    principal: Principal = Depends(security.require_role("operator", "admin")),
):
    tag = db.get(EquipmentTag, tag_id)
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tag, k, v)
    equipment_service.add_history(
        db, tag, event="updated", from_status=tag.status, to_status=tag.status,
        reason=payload.reason, changed_by=principal.user_id, commit=False,
    )
    db.commit()
    db.refresh(tag)
    return tag


@router.post("/{tag_id}/inbound", response_model=TagOut)
def inbound(
    tag_id: str,
    payload: InboundRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(security.require_role("operator", "admin")),
):
    tag = db.get(EquipmentTag, tag_id)
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return equipment_service.inbound(db, tag, notes=payload.notes, changed_by=principal.user_id)


@router.post("/{tag_id}/discard", response_model=TagOut)
def discard(
    tag_id: str,
    payload: DiscardRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: Principal = Depends(security.require_role("operator", "admin")),
):
    tag = db.get(EquipmentTag, tag_id)
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    try:
        tag = equipment_service.discard(db, tag, reason=payload.reason, changed_by=principal.user_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    audit_service.record(
        db, "equipment.discard", principal=principal, entity_type="equipment_tag",
        entity_id=tag.id, meta={"reason": payload.reason},
        ip_address=request.client.host if request.client else None,
    )
    return tag


@router.get("/{tag_id}/history", response_model=list[HistoryOut])
def history(tag_id: str, db: Session = Depends(get_db), _: Principal = Depends(security.get_current_principal)):
    if not db.get(EquipmentTag, tag_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    return db.execute(
        select(EquipmentStatusHistory)
        .where(EquipmentStatusHistory.equipment_id == tag_id)
        .order_by(EquipmentStatusHistory.changed_at.asc())
    ).scalars().all()
