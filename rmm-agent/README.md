# RMM Agent — Phase 2

The consent-aware endpoint agent. It connects to the Phase 1 server over WSS,
reports inventory, sends heartbeats, auto-reconnects, and — only during an
explicitly started session — streams the screen and applies the admin's mouse
and keyboard input.

## Design contract (intentional, do not weaken)

- **Visible.** A tray icon is shown the whole time the agent runs and reflects
  status (connecting / online / in-session). When a session starts, the user
  gets an OS notification. This is the consent surface for the people on the
  monitored machines.
- **No keylogging.** Input is *injected* via `pynput` Controllers during an
  active session; the agent never installs a Listener that would capture the
  local user's own keystrokes. `agent/input_control.py` is Controllers-only by
  construction.
- **Session-gated.** Screen capture and input injection run *only* while a
  session is active. No session = no capture. Each session is announced and
  logged on the server (`RemoteSession.user_notified = True`).

## Layout

```
rmm-agent/
├── agent/
│   ├── main.py            entrypoint: tray + connection loop
│   ├── config.py          config.json + RMM_* env overrides
│   ├── protocol.py        message envelope (mirrors the server)
│   ├── inventory.py       hostname/os/cpu/ram via platform + psutil
│   ├── connection.py      WSS client: auth, heartbeat, reconnect, dispatch
│   ├── session.py         session state machine; gates streaming + input
│   ├── screen.py          mss capture + Pillow JPEG encode
│   ├── input_control.py   pynput Controllers (injection only)
│   └── presence.py        tray icon + notifications (headless fallback)
├── config.example.json    copy to config.json and fill in token
├── dev_admin.py           drive a real session for testing (pre-Electron)
├── tests_e2e.py           live-server end-to-end tests
├── build/                 PyInstaller notes (.exe / .app) — Phase 8
└── service/               auto-start notes — Phase 3
```

## Install (Parrot OS / Linux dev box)

```bash
cd rmm-agent
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip && pip install -r requirements.txt
```

On Linux the tray/capture libs need an X session. On a headless box, run with
`--headless` (skips the tray) — the agent still connects, reports inventory,
and streams once a session starts.

## Configure

```bash
cp config.example.json config.json
# edit config.json: set server_url (wss://156.67.25.167:8765) and paste the
# one-time agent token printed by the server at machine enrollment.
```

`config.json` is git-ignored — it holds the per-machine token.

## Run

```bash
python -m agent.main            # tray icon if a display is present
python -m agent.main --headless # no tray (dev/build servers)
python -m agent.main --server wss://156.67.25.167:8765 --token <token> -v
```

The agent connects, appears **online** in the admin snapshot, and reports
inventory. It stays idle (no capture) until an admin starts a session.

## End-to-end test against the live Phase 1 server

1. Start the server (see the server README) and confirm `/health` is ok.
2. Register an admin, log in, and enroll a machine — copy the one-time token.
3. Put the token + server URL in `config.json`, then run `python -m agent.main`.
4. In another terminal, drive a real session with the dev tool:

```bash
python dev_admin.py --server http://localhost:8765 \
  --email you@example.com --password yourpass \
  --machine-id <uuid-from-enrollment> --seconds 5
```

You should see the agent raise a "session started" notification, the dev tool
report frames received, and a `mouse_move` land on the screen. The real admin
console arrives in Phase 4/5.

## Offline / headless self-test (no server, no display)

```bash
python tests_e2e.py
```

Spins up a local WebSocket server, swaps screen/input for headless fakes, and
verifies: connect → welcome → hello → heartbeat → session_start → frames →
input applied → session_stop, plus reconnect-after-drop.
