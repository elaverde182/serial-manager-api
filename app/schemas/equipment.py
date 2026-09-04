"""Schemas de equipos (equipment_tags) y su historial."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EquipmentTypeMini(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    category: str
    model: str


class TagCreate(BaseModel):
    country_code: str
    laboratory_id: int | None = None
    equipment_type_id: int | None = None
    reason: str | None = None
    notes: str | None = None
    client_op_id: str | None = None


class TagBatchCreate(BaseModel):
    """Genera varios seriales de una vez con el mismo país/laboratorio/tipo de equipo."""

    country_code: str
    laboratory_id: int | None = None
    equipment_type_id: int | None = None
    reason: str | None = None
    notes: str | None = None
    quantity: int = Field(ge=1, le=50)


class TagUpdate(BaseModel):
    equipment_type_id: int | None = None
    reason: str | None = None
    notes: str | None = None


class DiscardRequest(BaseModel):
    reason: str  # dañado | ilegible | obsoleto | otro


class InboundRequest(BaseModel):
    notes: str | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    serial_code: str
    country_code: str
    laboratory_id: int | None = None
    consecutive: int
    random_code: str
    equipment_type_id: int | None = None
    status: str
    reason: str | None = None
    notes: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    event: str
    from_status: str | None = None
    to_status: str | None = None
    reason: str | None = None
    changed_by: int | None = None
    changed_at: datetime


class PageMeta(BaseModel):
    page: int
    size: int
    total: int


class TagPage(BaseModel):
    items: list[TagOut]
    meta: PageMeta
