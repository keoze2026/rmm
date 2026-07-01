"""Monitored machine (endpoint) model. Each agent enrolls as one Machine."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Machine(Base):
    __tablename__ = "machines"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Human-friendly label shown in the admin app.
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Per-machine secret the agent presents to authenticate over WSS.
    # Stored hashed; the plaintext is shown to the admin only once at enrollment.
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Short non-secret prefix to help the admin identify which token is which.
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    # --- Inventory reported by the agent on connect ---
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    os_name: Mapped[str | None] = mapped_column(String(64), nullable=True)       # windows / darwin
    os_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    os_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cpu_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_total_mb: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- State ---
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Machine {self.name} online={self.is_online}>"
