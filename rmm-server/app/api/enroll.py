"""Seamless auto-enrollment.

An installer carrying the shared enroll secret can self-register a machine and
receive its own unique token on first run. This is what makes install seamless:
the user runs the installer, the agent enrolls itself, no token handling.
"""
from __future__ import annotations

import logging
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

log = logging.getLogger("app.api.enroll")

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
    # True only when a support_code was supplied AND matched an open session.
    # The agent warns on False so a mis-typed/stale code stops failing silently.
    support_bound: bool = False


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
    support_bound = False
    code = payload.support_code.strip().upper() if payload.support_code else ""
    if code:
        sess = await db.scalar(
            select(SupportSession).where(SupportSession.code == code)
        )
        if sess and sess.status != "ended":
            sess.machine_id = machine.id
            sess.status = "joined"
            sess.joined_at = datetime.now(timezone.utc)
            await db.commit()
            support_bound = True
        else:
            # Never silent: an unmatched code is the difference between a
            # machine the admin can find under its session and one they can't.
            log.warning(
                "auto-enroll: support code %r matched no open session (machine %s)",
                code, machine.id,
            )

    detail = {"name": machine.name, "auto": True}
    if code:
        detail |= {"support_code": code, "support_bound": support_bound}
    await log_event(db, "machine.enrolled", actor="auto-enroll",
                    machine_id=machine.id, detail=detail)
    return AutoEnrollOut(
        machine_id=str(machine.id), agent_token=raw, support_bound=support_bound
    )