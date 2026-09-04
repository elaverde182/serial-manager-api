"""Schemas de impresión de etiquetas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PreviewRequest(BaseModel):
    equipment_id: str
    label_size_id: int
    barcode_type: str | None = None  # override opcional


class PreviewResponse(BaseModel):
    zpl: str
    preview_png_base64: str
    label_size: dict


class PrintRequest(BaseModel):
    equipment_id: str
    label_size_id: int
    copies: int = 1
    darkness: int = 15


class PrintResponse(BaseModel):
    print_job_id: int
    zpl: str


class PrintJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    equipment_id: str
    serial_code: str | None = None
    label_size_id: int
    copies: int
    darkness: int
    is_reprint: bool
    printed_by: int | None = None
    printed_at: datetime
