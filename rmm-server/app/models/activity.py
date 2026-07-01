"""Append-only activity/audit log for every significant action in the system."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # e.g. agent.connected, agent.disconnected, session.start, session.end,
    # machine.enrolled, machine.deleted, admin.login
    event: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    actor: Mapped[str | None] = mapped_column(String(255), nullable=True)  # admin email or machine name
    machine_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), index=True, nullable=True)
    admin_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ActivityLog {self.event} {self.created_at}>"
