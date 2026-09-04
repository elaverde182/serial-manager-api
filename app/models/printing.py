"""Modelo de impresiones / reimpresiones."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PrintJob(Base):
    __tablename__ = "print_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(
        String(26), ForeignKey("equipment_tags.id"), nullable=False
    )
    label_size_id: Mapped[int] = mapped_column(
        ForeignKey("label_sizes.id"), nullable=False
    )
    copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    darkness: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    zpl_generated: Mapped[str] = mapped_column(Text, nullable=False)
    is_reprint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    printed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    printed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
