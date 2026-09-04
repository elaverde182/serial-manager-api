"""Modelos del núcleo: consecutivos, equipos identificados e historial de estados."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Consecutive(Base):
    """Contador por país/laboratorio. Una fila por contador (se bloquea con FOR UPDATE)."""

    __tablename__ = "consecutives"
    __table_args__ = (
        UniqueConstraint("country_code", "laboratory_id", name="uq_seq_country_lab"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    country_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("countries.code"), nullable=False
    )
    laboratory_id: Mapped[int | None] = mapped_column(ForeignKey("laboratories.id"))
    current_value: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EquipmentTag(Base):
    """Tabla principal: un equipo identificado."""

    __tablename__ = "equipment_tags"
    __table_args__ = (
        # Defensa en profundidad: el consecutivo no se repite por país/laboratorio
        # aunque el bloqueo de fila fallara. El bucle de reintento toma otro número.
        UniqueConstraint(
            "country_code", "laboratory_id", "consecutive",
            name="uq_tag_country_lab_consec",
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True)  # ULID
    serial_code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    country_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("countries.code"), nullable=False
    )
    laboratory_id: Mapped[int | None] = mapped_column(ForeignKey("laboratories.id"))
    consecutive: Mapped[int] = mapped_column(BigInteger, nullable=False)
    random_code: Mapped[str] = mapped_column(String(20), nullable=False)
    equipment_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("equipment_types.id")
    )
    status: Mapped[str] = mapped_column(
        String(12), default="active", nullable=False
    )  # active | discarded
    reason: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    client_op_id: Mapped[str | None] = mapped_column(String(36), unique=True)

    history: Mapped[list[EquipmentStatusHistory]] = relationship(
        back_populates="equipment", cascade="all, delete-orphan"
    )


class EquipmentStatusHistory(Base):
    """Append-only: cada transición de estado de un equipo."""

    __tablename__ = "equipment_status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("equipment_tags.id"), nullable=False
    )
    event: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # created | inbound | discarded | updated
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str | None] = mapped_column(String(20))
    reason: Mapped[str | None] = mapped_column(String(255))
    changed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    equipment: Mapped[EquipmentTag] = relationship(back_populates="history")
