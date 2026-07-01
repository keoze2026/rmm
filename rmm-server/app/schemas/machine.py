"""Machine request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    notes: str | None = None


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    is_enabled: bool | None = None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    token_prefix: str
    hostname: str | None
    os_name: str | None
    os_version: str | None
    os_username: str | None
    ip_address: str | None
    cpu_model: str | None
    cpu_cores: int | None
    ram_total_mb: int | None
    agent_version: str | None
    notes: str | None
    is_enabled: bool
    is_online: bool
    last_seen_at: datetime | None
    created_at: datetime


class MachineEnrolled(MachineOut):
    """Returned only at creation / token-regeneration: includes plaintext token once."""
    agent_token: str
