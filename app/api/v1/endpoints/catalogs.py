"""Endpoints de catálogos: países, laboratorios, tipos, formatos de serial y tamaños de etiqueta."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.models.catalog import (
    Country,
    EquipmentType,
    Laboratory,
    LabelSize,
    SerialFormat,
)
from app.schemas.catalog import (
    CountryCreate,
    CountryOut,
    CountryUpdate,
    EquipmentTypeCreate,
    EquipmentTypeOut,
    EquipmentTypeUpdate,
    LabelSizeCreate,
    LabelSizeOut,
    LabelSizeUpdate,
    LaboratoryCreate,
    LaboratoryOut,
    LaboratoryUpdate,
    SerialFormatCreate,
    SerialFormatOut,
    SerialFormatUpdate,
)

router = APIRouter(tags=["catálogos"])
admin = security.require_role("admin")
# El supervisor puede gestionar el catálogo de modelos (equipment-types); el
# resto de catálogos sigue siendo solo del administrador.
manage_models = security.require_role("admin", "supervisor")
any_user = security.get_current_principal


# ---------------- Países ----------------
@router.get("/countries", response_model=list[CountryOut])
def list_countries(db: Session = Depends(get_db), _: object = Depends(any_user)):
    return db.execute(select(Country).order_by(Country.code)).scalars().all()


@router.post("/countries", response_model=CountryOut, status_code=201)
def create_country(payload: CountryCreate, db: Session = Depends(get_db), _: object = Depends(admin)):
    if db.get(Country, payload.code):
        raise HTTPException(status.HTTP_409_CONFLICT, "El país ya existe")
    country = Country(**payload.model_dump())
    db.add(country)
    db.commit()
    return country


@router.patch("/countries/{code}", response_model=CountryOut)
def update_country(code: str, payload: CountryUpdate, db: Session = Depends(get_db), _: object = Depends(admin)):
    country = db.get(Country, code)
    if not country:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "País no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(country, k, v)
    db.commit()
    return country


# ---------------- Laboratorios ----------------
@router.get("/laboratories", response_model=list[LaboratoryOut])
def list_labs(country: str | None = None, db: Session = Depends(get_db), _: object = Depends(any_user)):
    stmt = select(Laboratory)
    if country:
        stmt = stmt.where(Laboratory.country_code == country)
    return db.execute(stmt.order_by(Laboratory.id)).scalars().all()


@router.post("/laboratories", response_model=LaboratoryOut, status_code=201)
def create_lab(payload: LaboratoryCreate, db: Session = Depends(get_db), _: object = Depends(admin)):
    if not db.get(Country, payload.country_code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "País inexistente")
    lab = Laboratory(**payload.model_dump())
    db.add(lab)
    db.commit()
    db.refresh(lab)
    return lab


@router.patch("/laboratories/{lab_id}", response_model=LaboratoryOut)
def update_lab(lab_id: int, payload: LaboratoryUpdate, db: Session = Depends(get_db), _: object = Depends(admin)):
    lab = db.get(Laboratory, lab_id)
    if not lab:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Laboratorio no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(lab, k, v)
    db.commit()
    return lab


# ---------------- Tipos de equipo ----------------
@router.get("/equipment-types", response_model=list[EquipmentTypeOut])
def list_types(category: str | None = None, db: Session = Depends(get_db), _: object = Depends(any_user)):
    stmt = select(EquipmentType)
    if category:
        stmt = stmt.where(EquipmentType.category == category)
    return db.execute(stmt.order_by(EquipmentType.id)).scalars().all()


@router.post("/equipment-types", response_model=EquipmentTypeOut, status_code=201)
def create_type(payload: EquipmentTypeCreate, db: Session = Depends(get_db), _: object = Depends(manage_models)):
    et = EquipmentType(**payload.model_dump())
    db.add(et)
    db.commit()
    db.refresh(et)
    return et


@router.patch("/equipment-types/{type_id}", response_model=EquipmentTypeOut)
def update_type(type_id: int, payload: EquipmentTypeUpdate, db: Session = Depends(get_db), _: object = Depends(manage_models)):
    et = db.get(EquipmentType, type_id)
    if not et:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tipo no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(et, k, v)
    db.commit()
    return et


# ---------------- Formatos de serial ----------------
@router.get("/serial-formats", response_model=list[SerialFormatOut])
def list_formats(db: Session = Depends(get_db), _: object = Depends(admin)):
    return db.execute(select(SerialFormat).order_by(SerialFormat.id)).scalars().all()


@router.post("/serial-formats", response_model=SerialFormatOut, status_code=201)
def create_format(payload: SerialFormatCreate, db: Session = Depends(get_db), _: object = Depends(admin)):
    fmt = SerialFormat(**payload.model_dump())
    db.add(fmt)
    db.commit()
    db.refresh(fmt)
    return fmt


@router.patch("/serial-formats/{fmt_id}", response_model=SerialFormatOut)
def update_format(fmt_id: int, payload: SerialFormatUpdate, db: Session = Depends(get_db), _: object = Depends(admin)):
    fmt = db.get(SerialFormat, fmt_id)
    if not fmt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Formato no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(fmt, k, v)
    db.commit()
    return fmt


# ---------------- Tamaños de etiqueta ----------------
@router.get("/label-sizes", response_model=list[LabelSizeOut])
def list_label_sizes(db: Session = Depends(get_db), _: object = Depends(any_user)):
    return db.execute(select(LabelSize).order_by(LabelSize.id)).scalars().all()


@router.post("/label-sizes", response_model=LabelSizeOut, status_code=201)
def create_label_size(payload: LabelSizeCreate, db: Session = Depends(get_db), _: object = Depends(admin)):
    size = LabelSize(**payload.model_dump())
    db.add(size)
    db.commit()
    db.refresh(size)
    return size


@router.patch("/label-sizes/{size_id}", response_model=LabelSizeOut)
def update_label_size(size_id: int, payload: LabelSizeUpdate, db: Session = Depends(get_db), _: object = Depends(admin)):
    size = db.get(LabelSize, size_id)
    if not size:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tamaño no encontrado")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(size, k, v)
    db.commit()
    return size
