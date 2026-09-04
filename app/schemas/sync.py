"""Schemas de sincronización offline/online."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SyncOperation(BaseModel):
    client_op_id: str
    type: str  # create | update | discard | print
    entity_id: str | None = None
    payload: dict = {}


class SyncPushRequest(BaseModel):
    device_id: str
    operations: list[SyncOperation]


class SyncRejected(BaseModel):
    client_op_id: str
    reason: str


class SyncCreated(BaseModel):
    """Entidad creada en el push: permite al cliente reconciliar el serial
    provisional generado offline con el serial real asignado por el servidor."""

    client_op_id: str
    id: str
    serial_code: str
    consecutive: int
    country_code: str
    status: str


class SyncPushResponse(BaseModel):
    applied: list[str]
    created: list[SyncCreated] = []
    conflicts: list[SyncRejected]
    rejected: list[SyncRejected]


class SyncPullResponse(BaseModel):
    cursor: datetime | None
    items: list[dict]
