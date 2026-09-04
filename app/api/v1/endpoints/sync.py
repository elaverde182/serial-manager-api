"""Endpoints de sincronización offline/online."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.core.database import get_db
from app.identity.base import Principal
from app.models.sync import SyncLog
from app.schemas.sync import (
    SyncCreated,
    SyncPullResponse,
    SyncPushRequest,
    SyncPushResponse,
    SyncRejected,
)
from app.services import sync_service

router = APIRouter(prefix="/sync", tags=["sincronización"])
op_or_admin = security.require_role("operator", "admin")


@router.post("/push", response_model=SyncPushResponse)
def push(
    payload: SyncPushRequest,
    db: Session = Depends(get_db),
    principal: Principal = Depends(op_or_admin),
):
    applied, created, conflicts, rejected = sync_service.push(
        db,
        device_id=payload.device_id,
        operations=payload.operations,
        created_by=principal.user_id,
        role=principal.role,
    )
    return SyncPushResponse(
        applied=applied,
        created=[SyncCreated(**c) for c in created],
        conflicts=[SyncRejected(**c) for c in conflicts],
        rejected=[SyncRejected(**r) for r in rejected],
    )


@router.get("/pull", response_model=SyncPullResponse)
def pull(
    since: datetime | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(op_or_admin),
):
    cursor, items = sync_service.pull(db, since=since)
    return SyncPullResponse(cursor=cursor, items=items)


@router.get("/status")
def sync_status(
    device_id: str | None = None,
    db: Session = Depends(get_db),
    _: Principal = Depends(op_or_admin),
):
    stmt = select(func.count()).select_from(SyncLog)
    if device_id:
        stmt = stmt.where(SyncLog.device_id == device_id)
    total = db.execute(stmt).scalar_one()
    return {"device_id": device_id, "synced_operations": total}
