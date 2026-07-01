"""Dev-only admin driver — test the agent end-to-end before the Electron app.

Logs in to the Phase 1 server, opens the admin WebSocket, subscribes to a
machine, starts a session (which makes the agent notify its user and begin
streaming), counts the frames that arrive, optionally nudges the mouse to prove
remote control, then stops the session.

This is a throwaway harness for Phase 2 verification. The real admin console is
the Electron app in Phase 4/5.

Usage:
    python dev_admin.py --server http://localhost:8765 \
        --email you@example.com --password secret \
        --machine-id <uuid-from-enrollment> --seconds 5
"""
from __future__ import annotations

import argparse
import asyncio
import json
import ssl
import sys
import urllib.parse
import urllib.request

import websockets


def login(server: str, email: str, password: str) -> str:
    url = server.rstrip("/") + "/api/auth/login"
    data = urllib.parse.urlencode({"username": email, "password": password}).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode())
    return body["access_token"]


def ws_url(server: str, token: str) -> str:
    scheme = "wss" if server.startswith("https") else "ws"
    host = server.split("://", 1)[1].rstrip("/")
    return f"{scheme}://{host}/ws/admin?token={token}"


async def drive(args) -> int:
    token = login(args.server, args.email, args.password)
    print("[admin] logged in, JWT acquired")

    ssl_ctx = None
    if ws_url(args.server, token).startswith("wss"):
        ssl_ctx = ssl.create_default_context()
        if args.insecure:
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

    async with websockets.connect(ws_url(args.server, token), ssl=ssl_ctx,
                                  max_size=16 * 1024 * 1024) as ws:
        # Subscribe so the server routes this machine's frames to us.
        await ws.send(json.dumps({"type": "subscribe", "machine_id": args.machine_id}))
        await ws.send(json.dumps({
            "type": "command", "machine_id": args.machine_id,
            "action": "session_start", "payload": {"kind": "control"},
        }))
        print(f"[admin] session_start sent to {args.machine_id}; "
              f"collecting frames for {args.seconds}s")

        frames = 0
        nudged = False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + args.seconds
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=deadline - loop.time())
            except asyncio.TimeoutError:
                break
            msg = json.loads(raw)
            if msg.get("type") == "frame" and msg.get("machine_id") == args.machine_id:
                frames += 1
                if not nudged and frames >= 3:
                    await ws.send(json.dumps({
                        "type": "command", "machine_id": args.machine_id,
                        "action": "mouse_move", "payload": {"x": 0.5, "y": 0.5},
                    }))
                    nudged = True
                    print("[admin] sent mouse_move (0.5, 0.5) to prove control")

        await ws.send(json.dumps({
            "type": "command", "machine_id": args.machine_id, "action": "session_stop",
        }))
        print(f"[admin] session_stop sent. Received {frames} frames.")
        return 0 if frames > 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Dev admin driver for agent testing")
    p.add_argument("--server", default="http://localhost:8765")
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--machine-id", required=True)
    p.add_argument("--seconds", type=float, default=5.0)
    p.add_argument("--insecure", action="store_true", help="skip TLS verify (self-signed)")
    args = p.parse_args()
    try:
        return asyncio.run(drive(args))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
