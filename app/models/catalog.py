"""Catálogos: países, laboratorios, tipos de equipo, formatos de serial y tamaños de etiqueta."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Country(Base):
    __tablename__ = "countries"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(10), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    laboratories: Mapped[list[Laboratory]] = relationship(back_populates="country")


class Laboratory(Base):
    __tablename__ = "laboratories"
    __table_args__ = (
        UniqueConstraint("country_code", "code", name="uq_lab_country_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("countries.code"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    country: Mapped[Country] = relationship(back_populates="laboratories")


class EquipmentType(Base):
    __tablename__ = "equipment_types"
    __table_args__ = (
        UniqueConstraint("category", "model", name="uq_type_category_model"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    # Longitud EXACTA del serial de fábrica de este modelo (12-16 según el
    # catálogo del cliente). Si es NULL, el serial usa el formato por
    # país/laboratorio (plantilla PAÍS-CONSECUTIVO-ALEATORIO).
    serial_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SerialFormat(Base):
    __tablename__ = "serial_formats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_code: Mapped[str | None] = mapped_column(
        String(3), ForeignKey("countries.code")
    )
    laboratory_id: Mapped[int | None] = mapped_column(ForeignKey("laboratories.id"))
    template: Mapped[str] = mapped_column(String(120), nullable=False)
    random_length: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    random_alphabet: Mapped[str] = mapped_column(
        String(40), default="ABCDEFGHJKLMNPQRSTUVWXYZ23456789", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class LabelSize(Base):
    __tablename__ = "label_sizes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    width_mm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    height_mm: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    dpi: Mapped[int] = mapped_column(Integer, default=203, nullable=False)
    zpl_template: Mapped[str] = mapped_column(Text, nullable=False)
    barcode_type: Mapped[str] = mapped_column(
        String(10), default="code128", nullable=False
    )  # code128 | qr | both
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
