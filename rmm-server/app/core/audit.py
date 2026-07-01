"""Helper to write append-only activity-log rows."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import ActivityLog


async def log_event(
    db: AsyncSession,
    event: str,
    *,
    actor: str | None = None,
    machine_id: uuid.UUID | None = None,
    admin_id: uuid.UUID | None = None,
    detail: dict | None = None,
    commit: bool = True,
) -> ActivityLog:
    row = ActivityLog(
        event=event,
        actor=actor,
        machine_id=machine_id,
        admin_id=admin_id,
        detail=detail,
    )
    db.add(row)
    if commit:
        await db.commit()
    return row
