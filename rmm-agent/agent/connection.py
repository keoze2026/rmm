"""WebSocket transport.

Owns the connection to /ws/agent: TLS, authentication via the per-machine
token, the heartbeat loop, automatic reconnect with exponential backoff, and
dispatch of inbound commands to the session manager.

Uses the `websockets` library. All outbound writes go through a lock so the
heartbeat and frame-stream tasks can share one socket safely.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import ssl

import websockets
from websockets.exceptions import ConnectionClosed

from agent import protocol
from agent.config import AgentConfig
from agent.inventory import collect as collect_inventory
from agent.presence import Presence
from agent.session import SessionManager
from agent.terminal import TerminalSession
from agent import files as fs

log = logging.getLogger("agent.connection")


class AgentConnection:
    def __init__(self, config: AgentConfig, presence: Presence) -> None:
        self.config = config
        self.presence = presence
        self._ws = None
        self._send_lock = asyncio.Lock()
        self._session = SessionManager(config, presence, self._send)
        self._stop = asyncio.Event()
        self.machine_id: str | None = None
        self._terminals: dict[str, TerminalSession] = {}

    # --- public ------------------------------------------------------------
    async def run_forever(self) -> None:
        """Connect, serve, and reconnect until stop() is called."""
        backoff = self.config.reconnect_min
        while not self._stop.is_set():
            try:
                self.presence.set_status("connecting", "Connecting…")
                await self._connect_and_serve()
                backoff = self.config.reconnect_min  # reset after a clean run
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("connection error: %s", exc)

            if self._stop.is_set():
                break

            self.presence.set_status("offline", "Reconnecting…")
            jitter = random.uniform(0, backoff * 0.25)
            wait = min(self.config.reconnect_max, backoff) + jitter
            log.info("reconnecting in %.1fs", wait)
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=wait)
            except asyncio.TimeoutError:
                pass
            backoff = min(self.config.reconnect_max, backoff * 2)

        await self._session.shutdown()

    def stop(self) -> None:
        self._stop.set()

    # --- connection lifecycle ---------------------------------------------
    def _ssl_context(self):
        if not self.config.agent_ws_url.startswith("wss"):
            return None
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = ssl.create_default_context()
        if self.config.tls_insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        return ctx

    async def _connect_and_serve(self) -> None:
        url = self.config.agent_ws_url
        log.info("connecting to %s", url.split("?")[0])
        async with websockets.connect(
            url,
            ssl=self._ssl_context(),
            ping_interval=20,
            ping_timeout=20,
            max_size=16 * 1024 * 1024,  # allow large frames
        ) as ws:
            self._ws = ws
            self.presence.set_status("online", "Connected")

            # Send inventory immediately after connect.
            await self._send(protocol.hello(collect_inventory()))

            hb_task = asyncio.create_task(self._heartbeat_loop())
            try:
                await self._read_loop()
            finally:
                hb_task.cancel()
                await self._stop_all_terminals()
                await self._session.stop_session(notify=False)
                self._ws = None

    async def _stop_all_terminals(self) -> None:
        for term in list(self._terminals.values()):
            try:
                await term.stop()
            except Exception:
                pass
        self._terminals.clear()

    async def _read_loop(self) -> None:
        assert self._ws is not None
        async for raw in self._ws:
            try:
                msg = json.loads(raw)
            except (ValueError, TypeError):
                continue
            await self._handle(msg)

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(self.config.heartbeat_interval)
                await self._send(protocol.heartbeat())
        except (asyncio.CancelledError, ConnectionClosed):
            pass

    # --- send (shared by all tasks) ---------------------------------------
    async def _send(self, message: dict) -> None:
        ws = self._ws
        if ws is None:
            return
        data = json.dumps(message)
        try:
            async with self._send_lock:
                await ws.send(data)
        except ConnectionClosed:
            pass

    # --- inbound dispatch --------------------------------------------------
    async def _handle(self, msg: dict) -> None:
        mtype = msg.get("type")

        if mtype == protocol.WELCOME:
            self.machine_id = msg.get("machine_id")
            log.info("enrolled as machine %s", self.machine_id)
            return

        if mtype == protocol.COMMAND:
            await self._handle_command(msg)
            return

    async def _handle_command(self, msg: dict) -> None:
        action = msg.get("action")
        payload = msg.get("payload") or {}
        admin_id = msg.get("admin_id")

        if action == protocol.ACTION_SESSION_START:
            kind = payload.get("kind", "control")
            await self._session.start_session(kind=kind, admin_id=admin_id)
            return

        if action == protocol.ACTION_SESSION_STOP:
            await self._session.stop_session()
            return

        if action == protocol.ACTION_PING:
            await self._send(protocol.agent_event("pong", admin_id=admin_id))
            return

        # Input actions only matter during an active session.
        if action in _INPUT_ACTIONS:
            await self._session.apply_input(action, payload)
            return

        # Terminal + file actions require an active (user-notified) session.
        if action in _TERM_ACTIONS or action in _FS_ACTIONS:
            if not self._session.active:
                await self._send(protocol.agent_event(
                    "error", reason="no_active_session", action=action))
                return
            if action in _TERM_ACTIONS:
                await self._handle_terminal(action, payload)
            else:
                await self._handle_files(action, payload)
            return

        log.debug("ignoring unknown action: %s", action)

    # --- terminal ----------------------------------------------------------
    async def _handle_terminal(self, action: str, payload: dict) -> None:
        term_id = str(payload.get("term_id", "default"))

        if action == protocol.ACTION_TERM_START:
            if term_id in self._terminals:
                return
            term = TerminalSession(term_id, self._send_terminal_output)
            try:
                await term.start(
                    cols=int(payload.get("cols", 80)),
                    rows=int(payload.get("rows", 24)),
                )
            except Exception as exc:
                await self._send(protocol.agent_event("term_error", term_id=term_id, reason=str(exc)))
                return
            self._terminals[term_id] = term
            await self._send(protocol.agent_event("term_started", term_id=term_id))
            return

        term = self._terminals.get(term_id)
        if term is None:
            return

        if action == protocol.ACTION_TERM_INPUT:
            await term.write(str(payload.get("data", "")))
        elif action == protocol.ACTION_TERM_RESIZE:
            term.resize(int(payload.get("cols", 80)), int(payload.get("rows", 24)))
        elif action == protocol.ACTION_TERM_STOP:
            await term.stop()
            self._terminals.pop(term_id, None)
            await self._send(protocol.agent_event("term_stopped", term_id=term_id))

    async def _send_terminal_output(self, term_id: str, data_b64: str) -> None:
        await self._send(protocol.terminal_output(term_id, data_b64))

    # --- files -------------------------------------------------------------
    async def _handle_files(self, action: str, payload: dict) -> None:
        if action == protocol.ACTION_FS_LIST:
            result = fs.list_dir(payload.get("path"))
            await self._send(protocol.agent_event("fs_list", **result))
            return

        if action == protocol.ACTION_FS_READ:
            transfer_id = str(payload.get("transfer_id", "t"))
            path = str(payload.get("path", ""))
            try:
                last = None
                for seq, total, chunk in fs.iter_file_chunks(path):
                    last = (seq, total)
                    await self._send(protocol.file_chunk(transfer_id, seq, total, chunk))
                if last is not None:
                    await self._send(protocol.file_chunk(transfer_id, last[0], last[1], "", eof=True))
            except OSError as exc:
                await self._send(protocol.agent_event("fs_error", transfer_id=transfer_id, reason=str(exc)))
            return

        if action == protocol.ACTION_FS_WRITE:
            path = str(payload.get("path", ""))
            try:
                fs.write_chunk(path, str(payload.get("data", "")), first=bool(payload.get("first", True)))
                if payload.get("last", True):
                    await self._send(protocol.agent_event("fs_write_done", path=path))
            except OSError as exc:
                await self._send(protocol.agent_event("fs_error", path=path, reason=str(exc)))
            return


_INPUT_ACTIONS = {
    protocol.ACTION_MOUSE_MOVE, protocol.ACTION_MOUSE_DOWN, protocol.ACTION_MOUSE_UP,
    protocol.ACTION_MOUSE_CLICK, protocol.ACTION_MOUSE_SCROLL,
    protocol.ACTION_KEY_DOWN, protocol.ACTION_KEY_UP, protocol.ACTION_KEY_TYPE,
}

_TERM_ACTIONS = {
    protocol.ACTION_TERM_START, protocol.ACTION_TERM_INPUT,
    protocol.ACTION_TERM_RESIZE, protocol.ACTION_TERM_STOP,
}
_FS_ACTIONS = {protocol.ACTION_FS_LIST, protocol.ACTION_FS_READ, protocol.ACTION_FS_WRITE}