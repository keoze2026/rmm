"""Remote-session recording.

Turns the agent's authoritative session lifecycle events into rows in
``remote_sessions`` plus ``session.start`` / ``session.end`` entries in the
activity log. Driven from the WS handler when the agent reports
``session_started`` / ``session_ended`` (and on agent disconnect, to close any
session left dangling).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_event
from app.models.session import RemoteSession


async def open_remote_session(
    db: AsyncSession,
    machine_id: uuid.UUID,
    *,
    admin_id: uuid.UUID | None = None,
    kind: str = "control",
    user_notified: bool = True,
) -> RemoteSession:
    """Create an active session row and log session.start."""
    session = RemoteSession(
        machine_id=machine_id,
        admin_id=admin_id,
        kind=kind,
        status="active",
        user_notified=user_notified,
    )
    db.add(session)
    await db.flush()  # populate session.id / started_at
    await log_event(
        db,
        "session.start",
        machine_id=machine_id,
        admin_id=admin_id,
        detail={"kind": kind, "session_id": str(session.id), "user_notified": user_notified},
        commit=False,
    )
    await db.commit()
    return session


async def close_remote_session(
    db: AsyncSession,
    machine_id: uuid.UUID,
    *,
    reason: str = "ended",
) -> RemoteSession | None:
    """Close the latest active session for a machine and log session.end."""
    stmt = (
        select(RemoteSession)
        .where(RemoteSession.machine_id == machine_id, RemoteSession.status == "active")
        .order_by(RemoteSession.started_at.desc())
    )
    session = (await db.scalars(stmt)).first()
    if session is None:
        return None

    now = datetime.now(timezone.utc)
    started = session.started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)

    session.status = "ended"
    session.ended_at = now
    session.duration_seconds = max(0, int((now - started).total_seconds()))

    await log_event(
        db,
        "session.end",
        machine_id=machine_id,
        admin_id=session.admin_id,
        detail={
            "session_id": str(session.id),
            "duration_seconds": session.duration_seconds,
            "reason": reason,
        },
        commit=False,
    )
    await db.commit()
    return session