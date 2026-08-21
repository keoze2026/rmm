"""Session lifecycle.

A session is the only time the agent captures the screen or injects input.
Starting one announces it to the user (notification + tray colour change) and
logs a session-start event to the server. Stopping it tears everything down
and notifies again. Nothing here runs unless an admin has explicitly started a
session for this machine.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable

from agent import protocol
from agent.config import AgentConfig
from agent.presence import Presence
from agent.screen import ScreenGrabber, list_monitors as _list_monitors
from agent.input_control import InputInjector

log = logging.getLogger("agent.session")


def _grab_tiles(grabber, keyframe: bool):
    """Tile capture with a full-frame fallback if anything goes wrong."""
    try:
        return grabber.grab_tiles(keyframe=keyframe)
    except Exception:
        return grabber.grab()

SendFn = Callable[[dict], Awaitable[None]]


class SessionManager:
    def __init__(self, config: AgentConfig, presence: Presence, send: SendFn) -> None:
        self.config = config
        self.presence = presence
        self.send = send

        self.active = False
        self.kind = "view"
        self._seq = 0
        self._frame_task: asyncio.Task | None = None
        self._grabber: ScreenGrabber | None = None
        self._injector: InputInjector | None = None
        # Single worker so the mss instance stays on one thread.
        self._capture_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="capture")

    # --- lifecycle ---------------------------------------------------------
    async def start_session(self, *, kind: str = "control", admin_id: str | None = None) -> None:
        if self.active:
            return
        self.active = True
        self.kind = kind

        # Announce to the user FIRST — consent surface before any capture.
        if self.config.notify_on_session:
            self.presence.notify(
                "Remote support session started",
                "An administrator has connected to this computer.",
            )
        self.presence.set_status("in_session", "Remote session active")
        await self.send(protocol.agent_event(
            "session_started", kind=kind, admin_id=admin_id, user_notified=True,
        ))

        # Spin up capture + (optionally) input injection.
        self._grabber = ScreenGrabber(
            self.config.monitor_index,
            quality=self.config.frame_quality,
            max_width=self.config.frame_max_width,
        )
        try:
            await asyncio.get_running_loop().run_in_executor(
                self._capture_pool, self._grabber.start
            )
        except Exception as exc:
            log.error("screen capture unavailable: %s", exc)
            await self.send(protocol.agent_event("session_error", reason=str(exc)))
            await self.stop_session(notify=False)
            return

        if self.config.allow_remote_input and kind == "control":
            self._injector = InputInjector(self._grabber.geometry or (1920, 1080))
            try:
                self._injector.start()
            except Exception as exc:  # pragma: no cover - platform dependent
                log.warning("input injection unavailable, going view-only: %s", exc)
                self._injector = None
                self.kind = "view"

        self._frame_task = asyncio.create_task(self._stream_loop())
        log.info("session started (kind=%s)", self.kind)

    async def stop_session(self, *, notify: bool = True) -> None:
        if not self.active:
            return
        self.active = False

        if self._frame_task:
            self._frame_task.cancel()
            try:
                await self._frame_task
            except (asyncio.CancelledError, Exception):
                pass
            self._frame_task = None

        if self._grabber:
            try:
                await asyncio.get_running_loop().run_in_executor(
                    self._capture_pool, self._grabber.close
                )
            except Exception:
                pass
            self._grabber = None
        self._injector = None

        self.presence.set_status("online", "Connected")
        if notify and self.config.notify_on_session:
            self.presence.notify(
                "Remote support session ended",
                "The administrator has disconnected.",
            )
        await self.send(protocol.agent_event("session_ended"))
        log.info("session stopped")

    async def shutdown(self) -> None:
        await self.stop_session(notify=False)
        self._capture_pool.shutdown(wait=False)

    # --- monitors (additive) ------------------------------------------------
    @property
    def current_monitor(self) -> int:
        """Which display an active session is capturing."""
        if self._grabber is not None:
            return self._grabber.monitor_index
        return self.config.monitor_index

    async def list_monitors(self) -> list[dict]:
        """Enumerate the guest's displays. Works with or without a session."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._capture_pool, _list_monitors)

    async def switch_monitor(self, index: int) -> tuple[int, int] | None:
        """Point an active session at another display.

        Returns the new (width, height), or None if no session is streaming.
        Capture keeps running throughout — grab() re-reads the monitor index
        each frame, so the stream simply continues on the new display.
        """
        grabber = self._grabber
        if not self.active or grabber is None:
            return None
        loop = asyncio.get_running_loop()
        size = await loop.run_in_executor(self._capture_pool, grabber.set_monitor, index)
        if size and self._injector is not None:
            # Keep pointer scaling correct for the new display geometry.
            self._injector.set_screen_size(size)
        return size

    # --- input -------------------------------------------------------------
    async def apply_input(self, action: str, payload: dict) -> None:
        if not self.active or self._injector is None:
            return
        # Injection is blocking; hand to the default executor.
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._injector.apply, action, payload)

    # --- streaming ---------------------------------------------------------
    async def _stream_loop(self) -> None:
        interval = 1.0 / max(0.5, self.config.frame_fps)
        loop = asyncio.get_running_loop()
        try:
            while self.active and self._grabber is not None:
                tick = loop.time()
                try:
                    # A keyframe every few seconds repairs any tile that went
                    # missing; everything between sends only what changed.
                    want_key = (self._seq % max(1, int(self.config.frame_fps * 5))) == 0
                    encoded = await loop.run_in_executor(
                        self._capture_pool, _grab_tiles, self._grabber, want_key
                    )
                except Exception as exc:
                    log.error("frame grab failed: %s", exc)
                    await asyncio.sleep(interval)
                    continue

                self._seq += 1
                if isinstance(encoded, dict):
                    # Tile frame: skip sending entirely when nothing moved.
                    if not encoded["tiles"]:
                        elapsed = loop.time() - tick
                        await asyncio.sleep(max(0.0, interval - elapsed))
                        continue
                    await self.send(protocol.frame_tiles(
                        encoded["tiles"], encoded["width"], encoded["height"],
                        monitor=self.config.monitor_index, seq=self._seq,
                        keyframe=encoded["keyframe"],
                    ))
                else:
                    await self.send(protocol.frame(
                        encoded.data_b64, encoded.width, encoded.height,
                        monitor=self.config.monitor_index, seq=self._seq,
                    ))

                elapsed = loop.time() - tick
                await asyncio.sleep(max(0.0, interval - elapsed))
        except asyncio.CancelledError:
            pass
