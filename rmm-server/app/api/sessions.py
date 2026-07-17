"""Read-only routes for session history and the activity/audit log."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.database import get_db
from app.models.activity import ActivityLog
from app.models.session import RemoteSession
from app.models.user import User
from app.schemas.session import ActivityLogOut, RemoteSessionOut

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=list[RemoteSessionOut])
async def list_sessions(
    machine_id: uuid.UUID | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[RemoteSession]:
    stmt = select(RemoteSession).order_by(RemoteSession.started_at.desc())
    if machine_id:
        stmt = stmt.where(RemoteSession.machine_id == machine_id)
    stmt = stmt.limit(limit).offset(offset)
    rows = await db.scalars(stmt)
    return list(rows)


@router.get("/activity", response_model=list[ActivityLogOut])
async def list_activity(
    event: str | None = None,
    machine_id: uuid.UUID | None = None,
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[ActivityLog]:
    stmt = select(ActivityLog).order_by(ActivityLog.created_at.desc())
    if event:
        stmt = stmt.where(ActivityLog.event == event)
    if machine_id:
        stmt = stmt.where(ActivityLog.machine_id == machine_id)
    stmt = stmt.limit(limit).offset(offset)
    rows = await db.scalars(stmt)
    return list(rows)
for missing in df.columns:
    values = np.sum(df[missing].is_null())
    print(missing, values)