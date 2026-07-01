"""Background task: mark agents offline if their heartbeat goes stale.

Guards against ungraceful disconnects where the socket close isn't observed.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.machine import Machine
from app.redis_client import ONLINE_AGENTS_KEY, redis_client
from app.ws.manager import manager


async def offline_reaper() -> None:
    interval = max(5, settings.AGENT_OFFLINE_AFTER // 2)
    while True:
        try:
            await asyncio.sleep(interval)
            cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
                seconds=settings.AGENT_OFFLINE_AFTER
            )
            online = await redis_client.hgetall(ONLINE_AGENTS_KEY)
            stale: list[str] = []
            for machine_id, last_seen_iso in online.items():
                try:
                    last_seen = dt.datetime.fromisoformat(last_seen_iso)
                except (ValueError, TypeError):
                    stale.append(machine_id)
                    continue
                if last_seen < cutoff and not manager.is_agent_local(machine_id):
                    stale.append(machine_id)

            for machine_id in stale:
                await redis_client.hdel(ONLINE_AGENTS_KEY, machine_id)
                async with AsyncSessionLocal() as db:
                    import uuid
                    machine = await db.get(Machine, uuid.UUID(machine_id))
                    if machine and machine.is_online:
                        machine.is_online = False
                        await db.commit()
                await manager.broadcast_to_admins(
                    {"type": "machine_status", "machine_id": machine_id, "online": False}
                )
        except asyncio.CancelledError:
            break
        except Exception:
            # Never let the reaper die on a transient error.
            await asyncio.sleep(interval)
