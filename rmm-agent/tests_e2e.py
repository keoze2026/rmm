"""End-to-end agent tests against a live local WebSocket server.

Swaps the real ScreenGrabber/InputInjector (which need a display) for headless
fakes so the full session->frame->input->stop path runs in CI. Exercises:
  1. connect -> welcome -> hello(inventory) -> heartbeat
  2. session_start -> notification + frames stream
  3. input commands applied during session
  4. session_stop -> streaming stops, events emitted
  5. reconnect with backoff after the server drops the socket
"""
from __future__ import annotations

import asyncio
import json
import sys

import websockets

import agent.session as session_mod
from agent.config import AgentConfig
from agent.connection import AgentConnection
from agent.presence import NullPresence
from agent.screen import EncodedFrame


# --- headless fakes --------------------------------------------------------
class FakeGrabber:
    def __init__(self, *a, **k):
        self.geometry = (1920, 1080)
        self.started = False

    def start(self):
        self.started = True

    def grab(self):
        # tiny valid payload; content doesn't matter for transport test
        return EncodedFrame(data_b64="ZmFrZQ==", width=1920, height=1080)

    def close(self):
        self.started = False


class FakeInjector:
    calls: list[tuple[str, dict]] = []

    def __init__(self, screen_size):
        self.screen_size = screen_size

    def start(self):
        pass

    def apply(self, action, payload):
        FakeInjector.calls.append((action, payload))


# --- test server (mimics Phase 1 /ws/agent) --------------------------------
class Recorder:
    def __init__(self):
        self.hello = None
        self.heartbeats = 0
        self.frames = 0
        self.events = []
        self.connections = 0


async def run_session_test() -> None:
    rec = Recorder()
    done = asyncio.Event()

    async def handler(ws):
        rec.connections += 1
        await ws.send(json.dumps({"type": "welcome", "machine_id": "test-machine-1"}))

        async def drive():
            # wait until hello arrives, then start a control session
            for _ in range(50):
                if rec.hello is not None:
                    break
                await asyncio.sleep(0.05)
            await ws.send(json.dumps({
                "type": "command", "action": "session_start",
                "payload": {"kind": "control"}, "admin_id": "admin-1",
            }))
            await asyncio.sleep(0.4)  # let some frames flow
            await ws.send(json.dumps({
                "type": "command", "action": "mouse_move",
                "payload": {"x": 0.5, "y": 0.5}, "admin_id": "admin-1",
            }))
            await ws.send(json.dumps({
                "type": "command", "action": "key_type",
                "payload": {"text": "hello"}, "admin_id": "admin-1",
            }))
            await asyncio.sleep(0.2)
            await ws.send(json.dumps({
                "type": "command", "action": "session_stop", "admin_id": "admin-1",
            }))
            await asyncio.sleep(0.2)
            done.set()

        drive_task = asyncio.create_task(drive())
        try:
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "hello":
                    rec.hello = msg.get("inventory")
                elif t == "heartbeat":
                    rec.heartbeats += 1
                elif t == "frame":
                    rec.frames += 1
                elif t == "agent_event":
                    rec.events.append(msg.get("event"))
        except websockets.ConnectionClosed:
            pass
        finally:
            drive_task.cancel()

    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        cfg = AgentConfig(
            server_url=f"ws://localhost:{port}",
            token="testtoken",
            heartbeat_interval=0.15,
            frame_fps=20.0,
            show_tray_icon=False,
            notify_on_session=True,
        )
        conn = AgentConnection(cfg, NullPresence())
        runner = asyncio.create_task(conn.run_forever())
        try:
            await asyncio.wait_for(done.wait(), timeout=8)
        finally:
            conn.stop()
            try:
                await asyncio.wait_for(runner, timeout=3)
            except asyncio.TimeoutError:
                runner.cancel()

    # --- assertions ---
    assert rec.hello is not None, "server never received hello/inventory"
    assert rec.hello.get("agent_version"), "inventory missing agent_version"
    assert rec.heartbeats >= 1, f"expected heartbeats, got {rec.heartbeats}"
    assert rec.frames >= 3, f"expected frames to stream, got {rec.frames}"
    assert "session_started" in rec.events, rec.events
    assert "session_ended" in rec.events, rec.events
    assert ("mouse_move", {"x": 0.5, "y": 0.5}) in FakeInjector.calls, FakeInjector.calls
    assert any(a == "key_type" for a, _ in FakeInjector.calls), FakeInjector.calls
    print(f"[session] ok: hello received, {rec.heartbeats} heartbeats, "
          f"{rec.frames} frames, events={rec.events}, "
          f"{len(FakeInjector.calls)} input cmds applied")


async def run_reconnect_test() -> None:
    attempts = {"n": 0}
    seen_two = asyncio.Event()

    async def handler(ws):
        attempts["n"] += 1
        # Accept, greet, then immediately drop to force a reconnect.
        await ws.send(json.dumps({"type": "welcome", "machine_id": "m"}))
        if attempts["n"] >= 2:
            seen_two.set()
        await ws.close()

    async with websockets.serve(handler, "localhost", 0) as server:
        port = server.sockets[0].getsockname()[1]
        cfg = AgentConfig(
            server_url=f"ws://localhost:{port}",
            token="t",
            heartbeat_interval=5.0,
            reconnect_min=0.1,
            reconnect_max=0.3,
            show_tray_icon=False,
        )
        conn = AgentConnection(cfg, NullPresence())
        runner = asyncio.create_task(conn.run_forever())
        try:
            await asyncio.wait_for(seen_two.wait(), timeout=6)
        finally:
            conn.stop()
            try:
                await asyncio.wait_for(runner, timeout=3)
            except asyncio.TimeoutError:
                runner.cancel()

    assert attempts["n"] >= 2, f"agent did not reconnect (attempts={attempts['n']})"
    print(f"[reconnect] ok: agent reconnected after drop ({attempts['n']} connects)")


async def main() -> int:
    # patch capture/input with headless fakes
    session_mod.ScreenGrabber = FakeGrabber
    session_mod.InputInjector = FakeInjector

    await run_session_test()
    await run_reconnect_test()
    print("\nALL AGENT TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
