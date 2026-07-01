"""Async Redis client + helpers for online-state tracking and pub/sub routing."""
from __future__ import annotations

import redis.asyncio as redis

from app.config import settings

# Decoded responses so we work with str, not bytes.
redis_client: redis.Redis = redis.from_url(
    settings.redis_url,
    encoding="utf-8",
    decode_responses=True,
)

# Key helpers ---------------------------------------------------------------
ONLINE_AGENTS_KEY = "rmm:online_agents"          # hash: machine_id -> last_seen_iso
AGENT_NODE_KEY = "rmm:agent_node"                # hash: machine_id -> worker/node id
ADMIN_CHANNEL = "rmm:admin_events"               # pub/sub: events fanned out to admins
AGENT_CHANNEL_PREFIX = "rmm:agent_cmd:"          # pub/sub per-agent command channel


def agent_channel(machine_id: str) -> str:
    return f"{AGENT_CHANNEL_PREFIX}{machine_id}"


async def ping() -> bool:
    try:
        return await redis_client.ping()
    except Exception:
        return False


async def close_redis() -> None:
    await redis_client.aclose()
