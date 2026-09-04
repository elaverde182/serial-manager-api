"""Schemas de auditoría."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int | None = None
    actor_label: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    meta: dict | None = Field(default=None)
    ip_address: str | None = None
    created_at: datetime
