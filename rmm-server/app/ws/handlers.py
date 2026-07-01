"""WebSocket endpoints for agents and admins.

Agent endpoint  : /ws/agent?token=<agent_token>
Admin endpoint  : /ws/admin?token=<jwt_access_token>

Phase 1 scope: authentication, enrollment/inventory sync, online-state
tracking, heartbeat, and the command/event routing plumbing. Screen-frame
streaming and input forwarding ride on this same envelope in later phases.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from sqlalchemy import select

from app.core.audit import log_event
from app.core.security import decode_access_token, hash_agent_token
from app.core.sessions import close_remote_session, open_remote_session
from app.database import AsyncSessionLocal
from app.models.machine import Machine
from app.models.user import User
from app.ws.manager import manager

router = APIRouter(tags=["websocket"])


# ---------------------------------------------------------------------------
# Agent endpoint
# ---------------------------------------------------------------------------
@router.websocket("/ws/agent")
async def agent_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token_hash = hash_agent_token(token)

    # Authenticate against the machine's stored token hash.
    async with AsyncSessionLocal() as db:
        machine = await db.scalar(select(Machine).where(Machine.token_hash == token_hash))
        if machine is None or not machine.is_enabled:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        machine_id = str(machine.id)

    await websocket.accept()
    await manager.register_agent(machine_id, websocket)

    # Tell the agent its identity.
    await websocket.send_text(json.dumps({"type": "welcome", "machine_id": machine_id}))

    try:
        async with AsyncSessionLocal() as db:
            machine = await db.get(Machine, uuid.UUID(machine_id))
            machine.is_online = True
            machine.last_seen_at = dt.datetime.now(dt.timezone.utc)
            client = websocket.client
            if client and not machine.ip_address:
                machine.ip_address = client.host
            await db.commit()
            await log_event(db, "agent.connected", actor=machine.name, machine_id=machine.id)

        await manager.broadcast_to_admins(
            {"type": "machine_status", "machine_id": machine_id, "online": True}
        )

        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            await _handle_agent_message(machine_id, msg)

    except WebSocketDisconnect:
        pass
    finally:
        await manager.unregister_agent(machine_id)
        async with AsyncSessionLocal() as db:
            machine = await db.get(Machine, uuid.UUID(machine_id))
            if machine:
                machine.is_online = False
                machine.last_seen_at = dt.datetime.now(dt.timezone.utc)
                await db.commit()
                await log_event(db, "agent.disconnected", actor=machine.name, machine_id=machine.id)
                # Close any session left active when the agent dropped.
                await close_remote_session(db, machine.id, reason="agent_disconnected")
        await manager.broadcast_to_admins(
            {"type": "machine_status", "machine_id": machine_id, "online": False}
        )


async def _handle_agent_message(machine_id: str, msg: dict) -> None:
    mtype = msg.get("type")

    if mtype == "heartbeat":
        await manager.touch_agent(machine_id)
        async with AsyncSessionLocal() as db:
            machine = await db.get(Machine, uuid.UUID(machine_id))
            if machine:
                machine.last_seen_at = dt.datetime.now(dt.timezone.utc)
                machine.is_online = True
                await db.commit()
        return

    if mtype == "hello":
        # Agent reports its inventory after connecting.
        inv = msg.get("inventory", {})
        async with AsyncSessionLocal() as db:
            machine = await db.get(Machine, uuid.UUID(machine_id))
            if machine:
                machine.hostname = inv.get("hostname") or machine.hostname
                machine.os_name = inv.get("os_name") or machine.os_name
                machine.os_version = inv.get("os_version") or machine.os_version
                machine.os_username = inv.get("os_username") or machine.os_username
                machine.cpu_model = inv.get("cpu_model") or machine.cpu_model
                machine.cpu_cores = inv.get("cpu_cores") or machine.cpu_cores
                machine.ram_total_mb = inv.get("ram_total_mb") or machine.ram_total_mb
                machine.agent_version = inv.get("agent_version") or machine.agent_version
                await db.commit()
                await manager.broadcast_to_admins(
                    {"type": "machine_inventory", "machine_id": machine_id, "inventory": inv}
                )
        return

    if mtype in ("frame", "agent_event", "file_chunk", "terminal_output"):
        # Persist session lifecycle (authoritative agent events) before relaying.
        if mtype == "agent_event":
            await _record_session_event(machine_id, msg)
        # Relay agent-originated payloads to subscribed admins.
        await manager.broadcast_to_admins({**msg, "machine_id": machine_id})
        return


async def _record_session_event(machine_id: str, msg: dict) -> None:
    event = msg.get("event")
    if event not in ("session_started", "session_ended"):
        return
    try:
        mid = uuid.UUID(machine_id)
    except (ValueError, TypeError):
        return
    admin_raw = msg.get("admin_id")
    try:
        admin_uuid = uuid.UUID(admin_raw) if admin_raw else None
    except (ValueError, TypeError):
        admin_uuid = None
    async with AsyncSessionLocal() as db:
        if event == "session_started":
            await open_remote_session(
                db,
                mid,
                admin_id=admin_uuid,
                kind=str(msg.get("kind", "control")),
                user_notified=bool(msg.get("user_notified", True)),
            )
        else:
            await close_remote_session(db, mid)


# ---------------------------------------------------------------------------
# Admin endpoint
# ---------------------------------------------------------------------------
@router.websocket("/ws/admin")
async def admin_ws(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload.get("sub"))
    except (jwt.PyJWTError, ValueError, TypeError):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await websocket.accept()
    conn_id = uuid.uuid4().hex
    manager.register_admin(conn_id, websocket)

    # Send a snapshot of all machines on connect.
    await _send_machines_snapshot(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            await _handle_admin_message(conn_id, str(user_id), msg)
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_admin(conn_id)


async def _send_machines_snapshot(websocket: WebSocket) -> None:
    async with AsyncSessionLocal() as db:
        rows = await db.scalars(select(Machine).order_by(Machine.name))
        machines = [
            {
                "id": str(m.id),
                "name": m.name,
                "is_online": m.is_online,
                "os_name": m.os_name,
                "hostname": m.hostname,
                "ip_address": m.ip_address,
                "last_seen_at": m.last_seen_at.isoformat() if m.last_seen_at else None,
            }
            for m in rows
        ]
    await websocket.send_text(json.dumps({"type": "machines_snapshot", "machines": machines}))


async def _handle_admin_message(conn_id: str, user_id: str, msg: dict) -> None:
    mtype = msg.get("type")

    if mtype == "subscribe":
        machine_id = msg.get("machine_id")
        if machine_id:
            manager.subscribe_admin(conn_id, machine_id)
        return

    if mtype == "unsubscribe":
        machine_id = msg.get("machine_id")
        if machine_id:
            manager.unsubscribe_admin(conn_id, machine_id)
        return

    if mtype == "command":
        machine_id = msg.get("machine_id")
        if not machine_id:
            return
        delivered = await manager.send_to_agent(
            machine_id,
            {"type": "command", "action": msg.get("action"), "payload": msg.get("payload"),
             "admin_id": user_id},
        )
        if not delivered:
            # Notify just this admin that the target is offline.
            await manager.broadcast_to_admins(
                {"type": "command_failed", "machine_id": machine_id, "reason": "agent_offline"}
            )
        return