# RMM — Project Status

Running log of what changed, what works, and what does not.
Newest entry first. Times are EAT (UTC+3).

---

## 2026-08-20 — Remote screen never rendered ("Starting session…" forever) — FIXED, VERIFIED LIVE

### The bug

Clicking **Join** left the console on "Starting session…" with a black screen.
It reproduced on two different endpoints (a Windows machine in India and a
local Linux machine), from two different browsers.

### How it was found

Evidence, in the order it was gathered:

| Check | Result | Meaning |
|---|---|---|
| Endpoint's OS notifications | "session started" / "session ended" fired | Commands reach the agent |
| `activity_logs` table | `session.start` / `session.end` rows written | The agent replies |
| Browser | no events, no frames | Nothing comes back |
| `docker compose logs … ws/admin` | 5 sockets, no exceptions | Not a reconnect flood |
| `redis-cli publish rmm:admin_events '{"type":"test"}'` | **`(integer) 0`** | **Zero subscribers — the relay is dead** |

That last line is the proof. `(integer) 0` means no process was listening on the
channel, so every frame and every `session_started` was published into nothing.

### Root cause

`rmm-server/app/ws/manager.py` — `_listen_admin_channel()` had no error
handling around its subscribe loop. One unexpected exception killed the task
permanently and nothing ever resubscribed. Everything else kept working
(agents connected, sessions recorded), which is why it looked like a UI bug.

The most likely killer was `_deliver_to_local_admins()`, which iterated
`self._admins.items()` while awaiting each send — any admin socket opening or
closing during that loop raises `RuntimeError: dictionary changed size during
iteration`.

### Fix

`rmm-server/app/ws/manager.py`, two changes, nothing else:

1. `_listen_admin_channel()` wrapped in a resubscribe loop with backoff, and it
   logs the failure instead of dying silently.
2. `_deliver_to_local_admins()` iterates `list(self._admins.items())`.

No protocol, API, schema or agent change.

### Deploying it

The server code is **baked into the Docker image** — a `git pull` alone does
nothing. The image has to be rebuilt:

```bash
cd /opt/rmm
git fetch origin && git checkout origin/main -- rmm-server/
docker compose up -d --build rmm-server
```

Verify — this must print `(integer) 1`, not `0`:

```bash
docker compose exec rmm-redis redis-cli publish rmm:admin_events '{"type":"test"}'
```

**Confirmed working 2026-08-20.** Returned `(integer) 1` after the rebuild, and
the remote screen renders. Remote control works.

---

## 2026-08-20 — Console redesign

Rebuilt the console as a single page, matching the supplied screenshot.
Everything is in `rmm-desktop/`; the server and agent were not touched.

### What was added

- **Four-column layout** — icon rail, Support panel, session list, detail column.
- **Session detail** — name, `Invite via: Code | Link`, the invite card with the
  join URL and code, Join button, waiting state.
- **10-icon tab rail** in the detail column.
- **Live screen thumbnail** once the guest joins; click for the full viewer.
- **Session list** fixed at 420px, detail column takes the rest.
- **Edit** focuses the Name field and selects it; the name persists locally.
- **Login** is email + password only — the server is taken from the page origin.
- **Cursor** over the remote screen is a normal pointer, was a crosshair.
- **Stale-session handshake** — sends `session_stop` before `session_start` and
  retries once, so a session left behind on the agent no longer wedges the view.

### Tabs — what actually works

| Tab | State |
|---|---|
| Session (invite/code/link/Join) | Working |
| System info | Working — full inventory |
| Session history | Working — `/api/sessions` |
| Logs | Working — `/api/activity` |
| Terminal | Working — opens the remote session |
| File transfer | Working |
| Download | Working |
| Chat | **Not available** — no agent command exists |
| Tools | **Not available** — no agent command exists |
| Locate | **Not available** — no agent command exists |

The last three need new message types in `agent/protocol.py` and
`agent/connection.py` plus relay in the server. Not built.

### Deploying the console

Static files, no restart needed:

```bash
cd /opt/rmm
git fetch origin && git checkout origin/main -- rmm-desktop/
cp -r /opt/rmm/rmm-desktop/web-dist/. /var/www/rmm/
```

nginx serves `/var/www/rmm` (**not** the git repo, and not `/var/www/rmm/admin`).
Verify with:

```bash
curl -s https://rmm.remotedesk247.com | grep -o 'index-[A-Za-z0-9_-]*\.js'
```

---

## Known issues / not fixed

- **Remote control feels slow** (noted 2026-08-20, open). Not the console —
  mouse moves are already throttled to one per animation frame. The agent
  streams 1600px-wide JPEG at quality 60, base64-encoded, at 8 fps: roughly
  2 MB/s over India → Germany → Kenya. The levers are agent *config* values,
  not code: `frame_max_width`, `frame_quality`, `frame_fps`. The connector's
  `config.json` is generated by `rmm-server/app/api/download.py`, which sets
  none of them, so every connector runs the defaults. `frame_max_width: 1280`
  and `frame_quality: 45` would roughly halve the payload. Not changed —
  that file is hand-maintained on the server.
- **Session rename is local only.** `support_sessions` has a `label` column but
  no endpoint to set it, so a renamed session resets on another machine.
- **Duplicate machine rows.** `agent/config.py` reads a support code out of the
  executable name; the always-on `rmm-agent.exe` matches as `"AGENT"`, which
  sends it down the never-cache-a-token path, so it re-enrols on every start.
- **`_listen_agent_channel()`** has the same die-silently shape that
  `_listen_admin_channel()` had. It only breaks one agent, not all of them, so
  it was left alone.
- **Chat / Tools / Locate** — icons present, no implementation.
- **`Dashboard.tsx`** has a pre-existing TypeScript error (`SupportPanel`
  declared but never used). Predates this work; the build ignores it.
- **GitHub token** sits in plaintext in `.git/config` on the laptop. Should be
  rotated and replaced with a credential helper or SSH.

---

## Environment cheat-sheet

| Thing | Where |
|---|---|
| Server | Contabo, `root@vmi3333575`, `/opt/rmm` |
| Console (web) | `/var/www/rmm` — served by nginx |
| Join page | `/var/www/rmm/join/` |
| Connector binaries | `/var/www/rmm/download/` |
| API + WebSocket | FastAPI in Docker, port 8765, proxied at `/api` and `/ws` |
| Laptop repo | `/home/hans/Desktop/rmm` |
| Build console | `cd rmm-desktop && npx vite build -c vite.web.config.ts` |
| Run console locally | `cd rmm-desktop && npx vite -c vite.web.config.ts --port 5173` |

**Server code lives in the Docker image.** Changes to `rmm-server/` need
`docker compose up -d --build rmm-server`, not just a pull.
