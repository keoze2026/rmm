"""Seamless auto-enrollment.

An installer carrying the shared enroll secret can self-register a machine and
receive its own unique token on first run. This is what makes install seamless:
the user runs the installer, the agent enrolls itself, no token handling.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_event
from app.core.security import generate_agent_token
from app.database import get_db
from app.models.machine import Machine
from app.models.support_session import SupportSession

router = APIRouter(prefix="/api/enroll", tags=["enroll"])


class AutoEnrollIn(BaseModel):
    enroll_secret: str
    name: str = Field(min_length=1, max_length=255)
    hostname: str | None = None
    os_name: str | None = None
    support_code: str | None = None


class AutoEnrollOut(BaseModel):
    machine_id: str
    agent_token: str


@router.post("", response_model=AutoEnrollOut)
async def auto_enroll(payload: AutoEnrollIn, db: AsyncSession = Depends(get_db)) -> AutoEnrollOut:
    secret = os.getenv("ENROLL_SECRET", "")
    if not secret or payload.enroll_secret != secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid enroll secret")
    raw, token_hash, prefix = generate_agent_token()
    machine = Machine(
        name=payload.name,
        hostname=payload.hostname,
        os_name=payload.os_name,
        token_hash=token_hash,
        token_prefix=prefix,
    )
    db.add(machine)
    await db.commit()
    await db.refresh(machine)

    # --- support session binding (additive) ---
    if payload.support_code:
        sess = await db.scalar(
            select(SupportSession).where(
                SupportSession.code == payload.support_code.strip().upper()
            )
        )
        if sess and sess.status != "ended":
            sess.machine_id = machine.id
            sess.status = "joined"
            sess.joined_at = datetime.now(timezone.utc)
            await db.commit()

    await log_event(db, "machine.enrolled", actor="auto-enroll",
                    machine_id=machine.id, detail={"name": machine.name, "auto": True})
    return AutoEnrollOut(machine_id=str(machine.id), agent_token=raw)