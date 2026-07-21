"""On-demand support sessions: create a code + link, look up by code/link."""
from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.deps import get_current_active_user
from app.database import get_db
from app.models.support_session import SupportSession
from app.models.user import User

router = APIRouter(prefix="/api/support", tags=["support"])

PUBLIC_BASE = getattr(settings, "public_base_url", "https://rmm.remotedesk247.com")

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_AMBIG = {"O": "0", "I": "1", "L": "1"}


def _gen_code(n: int = 6) -> str:
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(n))
    return "".join(_AMBIG.get(c, c) for c in raw)


class CreateOut(BaseModel):
    session_id: uuid.UUID
    code: str
    link: str
    status: str


class SupportOut(BaseModel):
    id: uuid.UUID
    code: str
    status: str
    label: str | None = None
    machine_id: uuid.UUID | None = None
    joined_at: datetime | None = None

    class Config:
        from_attributes = True


class ResolveOut(BaseModel):
    session_id: uuid.UUID
    code: str
    server_url: str
    status: str


@router.post("/create", response_model=CreateOut)
async def create_support_session(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> CreateOut:
    for _ in range(10):
        code = _gen_code()
        exists = await db.scalar(select(SupportSession).where(SupportSession.code == code))
        if not exists:
            break
    else:
        raise HTTPException(500, "could not allocate a code")

    link_token = secrets.token_urlsafe(24)
    sess = SupportSession(
        code=code,
        link_token=link_token,
        admin_id=user.id,
        status="waiting",
    )
    db.add(sess)
    await db.commit()
    await db.refresh(sess)

    link = f"{PUBLIC_BASE.rstrip('/')}/join/{link_token}"
    return CreateOut(session_id=sess.id, code=sess.code, link=link, status=sess.status)


@router.get("/list", response_model=list[SupportOut])
async def list_support_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> list[SupportSession]:
    stmt = (
        select(SupportSession)
        .where(SupportSession.status != "ended")
        .order_by(SupportSession.created_at.desc())
    )
    rows = await db.scalars(stmt)
    return list(rows)


@router.get("/resolve/{code}", response_model=ResolveOut)
async def resolve_code(code: str, db: AsyncSession = Depends(get_db)) -> ResolveOut:
    raw = code.strip()
    sess = await db.scalar(select(SupportSession).where(SupportSession.link_token == raw))
    if not sess:
        sess = await db.scalar(select(SupportSession).where(SupportSession.code == raw.upper()))
    if not sess or sess.status == "ended":
        raise HTTPException(404, "session not found or ended")

    ws = PUBLIC_BASE.replace("https://", "wss://").replace("http://", "ws://").rstrip("/")
    return ResolveOut(
        session_id=sess.id,
        code=sess.code,
        server_url=f"{ws}/ws/agent",
        status=sess.status,
    )


@router.post("/{session_id}/end")
async def end_support_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> dict:
    sess = await db.get(SupportSession, session_id)
    if not sess:
        raise HTTPException(404, "not found")
    sess.status = "ended"
    sess.ended_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}
