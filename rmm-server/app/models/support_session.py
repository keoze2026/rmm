"""Support session: an on-demand, code-based session a user joins to be helped.

Distinct from RemoteSession (which logs admin->machine control of an already
enrolled machine). A SupportSession is created by an admin, produces a short
join code + link, and the helped user downloads a connector that binds to it.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SupportSession(Base):
    __tablename__ = "support_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Short human code the user types in (e.g. "RG6092").
    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    # Longer opaque token used in the shareable link.
    link_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)

    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Once the user's connector enrolls, it becomes a machine; link it here.
    machine_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("machines.id", ondelete="SET NULL"), nullable=True
    )

    # waiting = created, nobody joined yet; joined = connector connected; ended.
    status: Mapped[str] = mapped_column(String(16), default="waiting", nullable=False)
    label: Mapped[str | None] = mapped_column(String(120), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<SupportSession code={self.code} status={self.status}>"