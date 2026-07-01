"""Session + activity log response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RemoteSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    machine_id: uuid.UUID
    admin_id: uuid.UUID | None
    kind: str
    status: str
    user_notified: bool
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None


class ActivityLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    event: str
    actor: str | None
    machine_id: uuid.UUID | None
    admin_id: uuid.UUID | None
    detail: dict | None
    created_at: datetime
