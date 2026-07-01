"""Remote session log: one row per admin->machine control/view session."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RemoteSession(Base):
    __tablename__ = "remote_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("machines.id", ondelete="CASCADE"), index=True, nullable=False
    )
    admin_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # view = screen streaming only, control = input forwarding, file/terminal as well.
    kind: Mapped[str] = mapped_column(String(32), default="view", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)  # active/ended

    # The agent is consent-aware: it confirms the user was notified the session started.
    user_notified: Mapped[bool] = mapped_column(default=True, nullable=False)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RemoteSession {self.kind} machine={self.machine_id} status={self.status}>"
