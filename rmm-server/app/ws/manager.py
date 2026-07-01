"""Connection manager for agents and admins.

Holds local socket registries and uses Redis pub/sub so that commands and
events route correctly even when agents and admins are connected to different
Uvicorn workers / nodes. This keeps the design correct for the multi-worker
VPS deployment while still working with a single local worker.

Message envelope: every WS message is JSON: {"type": "...", ...}.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import WebSocket

from app.redis_client import (
    ADMIN_CHANNEL,
    AGENT_NODE_KEY,
    ONLINE_AGENTS_KEY,
    agent_channel,
    redis_client,
)


class ConnectionManager:
    def __init__(self) -> None:
        # Locally-connected sockets on THIS worker.
        self._agents: dict[str, WebSocket] = {}        # machine_id -> ws
        self._admins: dict[str, WebSocket] = {}        # admin_conn_id -> ws
        # Which machines each admin is actively viewing (for frame routing later).
        self._admin_subscriptions: dict[str, set[str]] = {}
        self._node_id = uuid.uuid4().hex[:12]
        self._pubsub_task: asyncio.Task | None = None
        self._agent_listener_tasks: dict[str, asyncio.Task] = {}

    # --- lifecycle ---------------------------------------------------------
    async def start(self) -> None:
        """Subscribe to the admin fan-out channel for this node."""
        self._pubsub_task = asyncio.create_task(self._listen_admin_channel())

    async def stop(self) -> None:
        if self._pubsub_task:
            self._pubsub_task.cancel()
        for task in self._agent_listener_tasks.values():
            task.cancel()

    # --- agents ------------------------------------------------------------
    async def register_agent(self, machine_id: str, ws: WebSocket) -> None:
        self._agents[machine_id] = ws
        now = datetime.now(timezone.utc).isoformat()
        await redis_client.hset(ONLINE_AGENTS_KEY, machine_id, now)
        await redis_client.hset(AGENT_NODE_KEY, machine_id, self._node_id)
        # Listen for commands addressed to this agent from any node.
        self._agent_listener_tasks[machine_id] = asyncio.create_task(
            self._listen_agent_channel(machine_id)
        )

    async def unregister_agent(self, machine_id: str) -> None:
        self._agents.pop(machine_id, None)
        await redis_client.hdel(ONLINE_AGENTS_KEY, machine_id)
        await redis_client.hdel(AGENT_NODE_KEY, machine_id)
        task = self._agent_listener_tasks.pop(machine_id, None)
        if task:
            task.cancel()

    async def touch_agent(self, machine_id: str) -> None:
        """Refresh last-seen on heartbeat."""
        now = datetime.now(timezone.utc).isoformat()
        await redis_client.hset(ONLINE_AGENTS_KEY, machine_id, now)

    async def send_to_agent(self, machine_id: str, message: dict) -> bool:
        """Send a command to an agent, wherever it is connected.

        If connected locally, write directly; otherwise publish to its channel
        and let the owning node deliver it.
        """
        ws = self._agents.get(machine_id)
        if ws is not None:
            await ws.send_text(json.dumps(message))
            return True
        # Not local: is it online anywhere?
        if await redis_client.hexists(ONLINE_AGENTS_KEY, machine_id):
            await redis_client.publish(agent_channel(machine_id), json.dumps(message))
            return True
        return False

    def is_agent_local(self, machine_id: str) -> bool:
        return machine_id in self._agents

    # --- admins ------------------------------------------------------------
    def register_admin(self, conn_id: str, ws: WebSocket) -> None:
        self._admins[conn_id] = ws
        self._admin_subscriptions[conn_id] = set()

    def unregister_admin(self, conn_id: str) -> None:
        self._admins.pop(conn_id, None)
        self._admin_subscriptions.pop(conn_id, None)

    def subscribe_admin(self, conn_id: str, machine_id: str) -> None:
        self._admin_subscriptions.setdefault(conn_id, set()).add(machine_id)

    def unsubscribe_admin(self, conn_id: str, machine_id: str) -> None:
        self._admin_subscriptions.get(conn_id, set()).discard(machine_id)

    async def broadcast_to_admins(self, message: dict) -> None:
        """Fan out an event to admins on every node via Redis."""
        await redis_client.publish(ADMIN_CHANNEL, json.dumps(message))

    async def _deliver_to_local_admins(self, message: dict) -> None:
        dead: list[str] = []
        payload = json.dumps(message)
        target_machine = message.get("machine_id")
        for conn_id, ws in self._admins.items():
            # Frame messages only go to admins subscribed to that machine.
            if message.get("type") == "frame" and target_machine is not None:
                if target_machine not in self._admin_subscriptions.get(conn_id, set()):
                    continue
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(conn_id)
        for conn_id in dead:
            self.unregister_admin(conn_id)

    # --- redis listeners ---------------------------------------------------
    async def _listen_admin_channel(self) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(ADMIN_CHANNEL)
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                try:
                    data = json.loads(msg["data"])
                except (ValueError, TypeError):
                    continue
                await self._deliver_to_local_admins(data)
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(ADMIN_CHANNEL)
            await pubsub.aclose()

    async def _listen_agent_channel(self, machine_id: str) -> None:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(agent_channel(machine_id))
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                ws = self._agents.get(machine_id)
                if ws is None:
                    break
                try:
                    await ws.send_text(msg["data"])
                except Exception:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(agent_channel(machine_id))
            await pubsub.aclose()


manager = ConnectionManager()
