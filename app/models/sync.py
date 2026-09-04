"""Modelo de bitácora de sincronización offline/online."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.json_type import JSONType


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_op_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    device_id: Mapped[str | None] = mapped_column(String(80))
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(26))
    status: Mapped[str] = mapped_column(
        String(12), nullable=False
    )  # applied | conflict | rejected
    conflict_detail: Mapped[dict | None] = mapped_column(JSONType)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
