"""Endpoints de impresión de etiquetas (ZPL + vista previa + historial)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.identity.base import Principal
from app.models.catalog import Country, EquipmentType, LabelSize
from app.models.equipment import EquipmentTag
from app.models.printing import PrintJob
from app.schemas.printing import (
    PreviewRequest,
    PreviewResponse,
    PrintJobOut,
    PrintRequest,
    PrintResponse,
)
from app.services import label_service

router = APIRouter(tags=["impresión"])
op_or_admin = security.require_role("operator", "admin")


def _load(
    db: Session, equipment_id: str, label_size_id: int
) -> tuple[EquipmentTag, LabelSize, Country | None, EquipmentType | None]:
    tag = db.get(EquipmentTag, equipment_id)
    if not tag:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipo no encontrado")
    size = db.get(LabelSize, label_size_id)
    if not size:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tamaño de etiqueta no encontrado")
    country = db.get(Country, tag.country_code)
    # El modelo va en el pie de la etiqueta, entre el país y la fecha.
    et = db.get(EquipmentType, tag.equipment_type_id) if tag.equipment_type_id else None
    return tag, size, country, et


@router.post("/labels/preview", response_model=PreviewResponse)
def preview(payload: PreviewRequest, db: Session = Depends(get_db), _: Principal = Depends(op_or_admin)):
    tag, size, country, et = _load(db, payload.equipment_id, payload.label_size_id)
    zpl = label_service.render_zpl(tag, size, country, et)
    png = label_service.render_preview_png(tag, size, et)
    return PreviewResponse(
        zpl=zpl,
        preview_png_base64=png,
        label_size={
            "name": size.name,
            "width_mm": float(size.width_mm),
            "height_mm": float(size.height_mm),
            "dpi": size.dpi,
        },
    )


def _do_print(db, payload, principal, is_reprint: bool) -> PrintResponse:
    tag, size, country, et = _load(db, payload.equipment_id, payload.label_size_id)
    zpl = label_service.render_zpl(tag, size, country, et)
    job = PrintJob(
        equipment_id=tag.id,
        label_size_id=size.id,
        copies=payload.copies,
        darkness=payload.darkness,
        zpl_generated=zpl,
        is_reprint=is_reprint,
        printed_by=principal.user_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return PrintResponse(print_job_id=job.id, zpl=zpl)


@router.post("/labels/print", response_model=PrintResponse)
def print_label(payload: PrintRequest, db: Session = Depends(get_db), principal: Principal = Depends(op_or_admin)):
    return _do_print(db, payload, principal, is_reprint=False)


@router.post("/equipment-tags/{tag_id}/reprint", response_model=PrintResponse)
def reprint(
    tag_id: str,
    payload: PrintRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(op_or_admin),
):
    # Forzar que el equipo de la ruta coincida con el payload.
    payload.equipment_id = tag_id
    return _do_print(db, payload, principal, is_reprint=True)


@router.get("/print-jobs", response_model=list[PrintJobOut])
def list_print_jobs(
    equipment_id: str | None = None,
    serial: str | None = None,
    is_reprint: bool | None = None,
    type_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(security.get_current_principal),
):
    stmt = select(PrintJob, EquipmentTag.serial_code).join(
        EquipmentTag, PrintJob.equipment_id == EquipmentTag.id
    )
    if equipment_id:
        stmt = stmt.where(PrintJob.equipment_id == equipment_id)
    if serial:
        stmt = stmt.where(EquipmentTag.serial_code.like(f"%{serial}%"))
    if is_reprint is not None:
        stmt = stmt.where(PrintJob.is_reprint.is_(is_reprint))
    # El modelo vive en el equipo, no en el trabajo de impresión: se filtra por
    # el join que ya se hace para traer el serial.
    if type_id is not None:
        stmt = stmt.where(EquipmentTag.equipment_type_id == type_id)
    if date_from:
        stmt = stmt.where(PrintJob.printed_at >= date_from)
    if date_to:
        stmt = stmt.where(PrintJob.printed_at <= date_to)

    rows = db.execute(
        stmt.order_by(PrintJob.printed_at.desc()).limit(300)
    ).all()
    result = []
    for job, serial_code in rows:
        result.append(
            PrintJobOut(
                id=job.id,
                equipment_id=job.equipment_id,
                serial_code=serial_code,
                label_size_id=job.label_size_id,
                copies=job.copies,
                darkness=job.darkness,
                is_reprint=job.is_reprint,
                printed_by=job.printed_by,
                printed_at=job.printed_at,
            )
        )
    return result
