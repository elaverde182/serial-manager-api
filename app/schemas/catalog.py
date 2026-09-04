"""Schemas de catálogos."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# ----- Países -----
class CountryBase(BaseModel):
    code: str
    name: str
    prefix: str
    is_active: bool = True


class CountryCreate(CountryBase):
    pass


class CountryUpdate(BaseModel):
    name: str | None = None
    prefix: str | None = None
    is_active: bool | None = None


class CountryOut(CountryBase):
    model_config = ConfigDict(from_attributes=True)


# ----- Laboratorios -----
class LaboratoryBase(BaseModel):
    country_code: str
    code: str
    name: str
    is_active: bool = True


class LaboratoryCreate(LaboratoryBase):
    pass


class LaboratoryUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None


class LaboratoryOut(LaboratoryBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ----- Tipos de equipo -----
class EquipmentTypeBase(BaseModel):
    category: str
    model: str
    # Longitud exacta del serial de fábrica del modelo (12-16). NULL = usar
    # el formato por país/laboratorio.
    serial_length: int | None = Field(default=None, ge=4, le=40)
    is_active: bool = True


class EquipmentTypeCreate(EquipmentTypeBase):
    pass


class EquipmentTypeUpdate(BaseModel):
    category: str | None = None
    model: str | None = None
    serial_length: int | None = Field(default=None, ge=4, le=40)
    is_active: bool | None = None


class EquipmentTypeOut(EquipmentTypeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ----- Formatos de serial -----
class SerialFormatBase(BaseModel):
    country_code: str | None = None
    laboratory_id: int | None = None
    template: str = "{country}-{consecutive:06d}-{random}"
    random_length: int = 6
    random_alphabet: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    is_active: bool = True


class SerialFormatCreate(SerialFormatBase):
    pass


class SerialFormatOut(SerialFormatBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ----- Tamaños de etiqueta -----
class LabelSizeBase(BaseModel):
    name: str
    width_mm: Decimal
    height_mm: Decimal
    dpi: int = 203
    zpl_template: str
    barcode_type: str = "code128"  # code128 | qr | both
    is_default: bool = False
    is_active: bool = True


class LabelSizeCreate(LabelSizeBase):
    pass


class LabelSizeUpdate(BaseModel):
    name: str | None = None
    width_mm: Decimal | None = None
    height_mm: Decimal | None = None
    dpi: int | None = None
    zpl_template: str | None = None
    barcode_type: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


class LabelSizeOut(LabelSizeBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


class SerialFormatUpdate(BaseModel):
    template: str | None = None
    random_length: int | None = None
    random_alphabet: str | None = None
    is_active: bool | None = None
