# RMM — Project Status

## 2026-08-22 — Feature 6 (blank guest screen) + per-platform reality

### Feature 6: blank the guest's screen

Purpose: when controlling the guest, the **guest sees black** but the **admin
still sees and controls the real desktop**.

- First cut was wrong: it put a black window on the guest's screen, but the
  agent captures that same screen, so the admin also saw black — useless.
- **Windows fix (works):** the black window uses `SetWindowDisplayAffinity`
  with `WDA_EXCLUDEFROMCAPTURE` — visible to the person at the machine,
  excluded from screen capture, so the admin sees the real desktop behind it.
  ctypes only, no dependency. Needs Windows 10 2004+.
  *Caveat:* honored for certain by modern capture APIs; whether `mss`'s BitBlt
  path respects it must be confirmed on real Windows (couldn't verify in dev).
  Fallback if not: switch the Windows agent capture to the modern API.
- **Linux/Mac:** no simple equivalent. Blank-privacy is Windows-only for now.

### Tray icon — the real story

The icon CODE never changed. The arcs showed on a build made **locally on the
dev machine**, which could reach the system tray libraries. The **CI build**
does not bundle those libraries (GI typelibs + libappindicator), so it falls
back to pystray's `_xorg` backend, which paints a box.

- **Windows / Mac:** native tray backends, no such dependency — icon works.
- **Linux:** shows a box on CI builds until the typelibs are bundled. Parked;
  Linux is not the demo platform.

### Per-platform status (build agent-v2.6.2)

| Feature | Windows | macOS | Linux |
|---|---|---|---|
| Enrol / bind / stream | ✅ | ✅ | ✅ |
| Tile speed (changed-region) | ✅ | ✅ | ✅ |
| Tray icon (logo) | ✅ | ✅ | ❌ box (typelibs unbundled) |
| Screenshot/zoom/annotate/files | ✅ | ✅ | ✅ |
| Monitor switcher | ✅ | ✅ | ✅ |
| Blank guest screen (privacy) | ✅ (verify on HW) | ❌ | ❌ |

### Parked (post-demo)

- Linux tray icon: bundle GI typelibs + libappindicator in the spec (a wrong
  spec edit breaks all three builds, so do it isolated, not in a rushed build).
- Blank-privacy on macOS/Linux: needs a per-window capture-exclusion path.

---

## Fast diagnosis

Symptom first. Each row has the **one command that confirms it**, so you are
never guessing. Server = Contabo (`root@vmi3333575`), laptop = your machine.

| Symptom | Likely cause | Confirm with | Fix |
|---|---|---|---|
| Screen black, status says **Live** | Console bundle is older than the connector (e.g. connector sends tiles, console can't paint them) | `curl -s https://rmm.remotedesk247.com \| grep -o 'index-[A-Za-z0-9_-]*\.js'` — compare to `rmm-desktop/web-dist/index.html` | Redeploy the console from the **laptop** |
| Stuck on **"Starting session…"**, screen black, terminal/files also dead | Admin fan-out listener died — everything published to a channel with no subscriber | **SERVER:** `docker compose exec rmm-redis redis-cli publish rmm:admin_events '{"type":"test"}'` → must print **1**, not 0 | Fixed in `ws/manager.py` (resubscribe loop). If it recurs, restart `rmm-server` |
| Agent seems connected but ignores commands | Agent replies but nothing reaches the browser | **SERVER:** `... psql -c "select event,created_at from activity_logs order by created_at desc limit 10;"` — `session.start` rows mean the agent **is** answering | Fan-out, as above |
| Connector enrols but session never goes green | `config.json` wasn't beside the exe, so the code fell back to the filename | **SERVER:** `... psql -c "select detail->>'support_code' code, detail->>'support_bound' bound from activity_logs where event='machine.enrolled' order by created_at desc limit 5;"` — `AGENT`/`WINDOWS` + `false` is the tell | Run the connector from the unzipped folder, not `RemoteSupportAgent-Setup.exe`. Check `_BINARIES` points at `.exe`, not `.zip` (a `.zip` there makes a zip-inside-a-zip) |
| Download button returns `{"detail":"Not Found"}` | Join page URL doesn't match the route prefix | **SERVER:** `docker exec rmm-rmm-server-1 grep -n "prefix=\|CONNECTOR_DIR\|DOWNLOAD_DIR" /app/app/api/download.py` | Make the join page path match the prefix the container actually runs |
| Download says "connector build not available" | Route reads a directory the files aren't in | **SERVER:** `docker exec rmm-rmm-server-1 ls -la /app/web/download` and `ls -la /var/www/rmm/download` | Bind-mount the host folder to the path the route reads (already in `docker-compose.yml`) |
| Tray icon is a coloured box (Linux) | `pystray` fell back to `_xorg`, which paints a rectangle by design | **LAPTOP:** `python -c "import pystray; print(pystray.Icon.__module__)"` — `_xorg` is the fault, `_appindicator` is correct | `gi` must be bundled; the spec does this on Linux. No amount of redrawing fixes `_xorg` |
| Remote control slow / low fps | Guest uplink saturated, or two streams competing | Read the **fps · kbps** readout in the viewer toolbar | ~2 fps at ~1 Mbps = link-limited. Tile streaming fixes it. Close extra console tabs — the thumbnail holds its own session |
| Picture renders small in a big black area | Canvas smaller than the viewer and CSS only limits size | Look at `frame_max_width` in the connector's `config.json` | Canvas uses `h-full w-full object-contain`; raise `frame_max_width` |
| New connector feature does nothing | Old connector still installed, or the singleton lock blocked the new one | On the guest: is the old process still running? | Kill it first: `pkill -f rmm-connector`, then download fresh. **Settings bake in at download time** |
| Console changes don't appear after deploy | Copied to the wrong place, or ran the `scp` on the server | `curl ... \| grep -o 'index-...js'` | nginx serves **`/var/www/rmm`**, not the git repo. Deploy from the **laptop** |
| Server won't start after an edit | Syntax error — a stray keystroke is enough | **SERVER:** `docker compose logs --tail=50 rmm-server` | The running container keeps working until rebuilt, so fix before `up --build` |

### Two rules that would have saved the most time

1. **Every command belongs to one machine.** Laptop builds and pushes; server
   pulls, mounts and rebuilds. Running one on the other wastes a cycle and
   looks like a code failure.
2. **Measure before changing.** The lag was "fixed" three times by lowering
   quality before the fps readout showed 2 fps at 930 kbps — link-limited, so
   quality was never the lever.

---

Running log of what changed, what works, and what does not.
Newest entry first. Times are EAT (UTC+3).

---

## 2026-08-21 — Remote control was slow: fixed by streaming only what changed

### Measured, not guessed

Added a live fps/bandwidth readout to the viewer. It showed **2 fps at
930 kbps** — about 58 KB per frame, on a guest uplink that tops out near
1 Mbps. Lowering quality three times barely helped, because the problem was
never quality.

### Cause

The agent sent a **full JPEG of the entire screen, every frame**, base64
wrapped (+33%). A desktop sitting still cost exactly as much as one playing
video. Commercial tools do not work this way — they send only the parts of the
screen that changed.

### Fix

- `screen.py` — `grab_tiles()`: splits the frame into an 8x6 grid, compares
  each tile with the previous frame, encodes only the ones that differ.
- `session.py` — streams tiles, sends a full keyframe every 5s to repair
  anything missed, and sends **nothing at all** when no tile changed.
- `protocol.py` — `frame_tiles()`. Reuses `type: "frame"` deliberately: the
  server relays a fixed set of message types and a new one would be dropped,
  so **the server needed no change**. Consumers tell them apart by `tiles`.
- `useRemoteSession.ts` — paints tiles onto a persistent surface and hands the
  composited result to `onFrame`, so the viewer and thumbnail are unchanged.
- Old connectors keep sending full frames and still render.

Also: the detail-panel thumbnail is now **opt-in**. It held its own session and
competed with the viewer for the same uplink whenever a session was selected.

Commit `558df07`, tag `agent-v2.4.0`.

### Expected result

On a still or lightly-changing desktop, roughly 10-20 fps at the same
bandwidth, and quality can go back up.

### Deployed

| Piece | State |
|---|---|
| Console (`index-DceKpZ9-.js`) | live |
| Windows connector | shipped |
| Mac connector | shipped |
| Linux connector | shipped, `chmod +x` done |

Guests must download a **fresh** connector — the old one keeps sending full
frames, and frame settings bake in at download time.

### Also fixed today

- File transfer had no feedback at all; the viewer now shows "Sent to guest" or
  the actual error. Files land on the guest's **Desktop**.
- Windows connector produced a zip-inside-a-zip, which separated `config.json`
  from the exe, so the support code fell back to the filename and enrolled as
  `AGENT` with `bound=false`. Fixed by pointing `_BINARIES["windows"]` at the
  `.exe` rather than a `.zip`.

---

## 2026-08-21 — Tray icon fixed on all three platforms; agents shipped

### The tray icon was never a drawing problem

Linux showed a coloured box no matter what was drawn — a dot on a square, a
monitor glyph, arcs on a tile, arcs on transparency. Four different images,
same box.

Cause: `pystray` was falling back to `pystray._xorg`, which paints a flat
rectangle by design. PyGObject was not bundled, so the AppIndicator backend
could not load. Proven with:

```
backend module: pystray._xorg     <- the flat-rectangle fallback
build venv: no 'gi'               <- AppIndicator cannot load
system python: ayatana OK         <- the machine supports it
```

### Fix

- `presence.py` — prefers AppIndicator/GTK on Linux before pystray chooses;
  Linux-only and guarded by `sys.platform`.
- `rmm-agent.spec` — bundles `gi` on Linux only. Icon-only change.
- Icon itself — the product's broadcast mark: white arcs on transparency with
  a small status dot (green online, blue in-session, amber connecting, grey
  offline). Drawn, not a bundled asset: a one-file PyInstaller build has no
  dependable asset path at runtime.

Windows and macOS needed no change — their native backends render the image
directly, which is why only Linux was broken.

Commit `e6b1b2a`, tag `agent-v2.3.0`.

### Shipped

| Platform | Built | Deployed | Verified |
|---|---|---|---|
| Linux | locally, then CI (33 MB) | yes | **icon confirmed working in tray** |
| Windows | CI | yes — `rmm-connector-windows.exe` | pending test |
| Mac | CI | yes — `rmm-connector-mac.zip` | pending test |

### Shipping a connector, start to finish

```bash
# laptop — download the three artifacts from the Actions run first
cd ~/Downloads
unzip -o rmm-agent-windows.zip -d win
unzip -o rmm-agent-mac.zip -d mac

# mac: GitHub's artifact zip strips the exec bit, so restore it before re-zipping
chmod +x "mac/Remote Support Agent.app/Contents/MacOS/rmm-agent" mac/rmm-agent
cd mac && zip -ry ../rmm-connector-mac.zip "Remote Support Agent.app" rmm-agent config.json && cd ..

scp win/rmm-connector-windows.exe root@rmm.remotedesk247.com:/var/www/rmm/download/rmm-connector-windows.exe
scp rmm-connector-mac.zip        root@rmm.remotedesk247.com:/var/www/rmm/download/rmm-connector-mac.zip
scp <linux binary>               root@rmm.remotedesk247.com:/var/www/rmm/download/rmm-connector-linux
```

```bash
# server
chmod +x /var/www/rmm/download/rmm-connector-linux
```

Testing on a machine that already runs an agent: **kill the old one first** or
the singleton lock makes the new binary exit silently.

```bash
pkill -f rmm-connector; pkill -f rmm-agent
```

### Open

- Linux connector built locally was 213 MB (`--system-site-packages` pulled in
  the whole system). The CI build is 33 MB — use CI's. Local builds are for
  testing only.
- Remote-control lag: still on the default 1600px / quality 60 / 8 fps. The
  two-key fix in `download.py` is written up in the entry below.

---

## 2026-08-21 — Earlier: Linux agent rebuilt; speed tuning

### Tray icon — fixed

`presence.py` drew a 32px coloured dot on a 64px dark square. Trays downscaled
that into a faded box on Linux and showed nothing usable on Windows/macOS.
There was never an icon asset — it was always drawn.

Now: a full-bleed rounded square in the status colour with a white screen
glyph, 128px, still legible at 16–22px. Green online, blue in-session, amber
connecting, grey offline.

Drawn rather than bundled on purpose — a one-file PyInstaller build has no
dependable asset path at runtime, and pystray accepts a PIL image directly on
all three platforms. **No spec change, no new dependency.**

Commit `841c1a8`, tagged `agent-v2.2.0`.

### Builds

| Platform | State |
|---|---|
| Linux | **Built locally** → `/tmp/rmm-connector-linux` (22 MB). Has the tray icon *and* the monitor switcher. |
| Windows | Needs GitHub Actions — PyInstaller only builds for the OS it runs on |
| Mac | Needs GitHub Actions |

Trigger Windows/Mac: `git push origin main && git push origin agent-v2.2.0`

### Deploying a connector

```bash
# laptop
scp /tmp/rmm-connector-linux root@vmi3333575:/var/www/rmm/download/rmm-connector-linux
# server
chmod +x /var/www/rmm/download/rmm-connector-linux
```

Testing on a machine that already runs an agent: **kill the old one first** or
the singleton lock makes the new binary exit silently.

```bash
pkill -f rmm-connector; pkill -f rmm-agent
```

### Remote control lag — cause and fix

Not the console. Mouse moves are already throttled to one per animation frame.
The agent streams **1600px-wide JPEG at quality 60, base64, 8 fps** — roughly
2 MB/s over India → Germany → Kenya.

Fix without rebuilding anything: `download.py` writes the connector's
`config.json` at download time, so adding two keys to that dict applies to
every new connector.

```python
        "frame_max_width": 1280,
        "frame_quality": 45,
```

Then `docker compose up -d --build rmm-server` — drops live WebSockets, so run
it with no session active. Roughly halves the payload.

### Console features — live and confirmed

Screenshot, zoom in/out, annotate, send file to guest, get file from guest.
All five working in the deployed console. Monitor switcher is built but needs
the new agent on each endpoint.

---

## 2026-08-20 — Six viewer features requested; five added, one skipped

Strictly additive. Existing behaviour verified unchanged afterwards.

### Added

| Feature | How | Agent change |
|---|---|---|
| Screenshot | `canvas.toBlob()` → downloads `<machine>-<timestamp>.png` | none |
| Zoom in / out / reset | CSS transform on the frame canvas; `scale(1)` by default | none |
| Annotate | Separate overlay canvas above the frame, red pen + clear. Admin-side only — pointer events are off unless the pen is on, so the remote input path is untouched when idle | none |
| Send file to guest | File picker → chunked `fs_write` (192 KB chunks), lands in the guest's home folder | none — uses the existing action |
| Get file from guest | `fs_read` → assembles the returned `file_chunk`s and saves | none — uses the existing action |
| Monitor switcher | New `monitors_list` / `monitor_select` actions; agent replies on the existing `agent_event` envelope | **new** |

### Skipped, deliberately

**Blank the guest's screen** — needs a fullscreen always-on-top black window on
the guest. `tkinter` is excluded in the PyInstaller spec and `pystray`/`PIL`
cannot make one, so it would need a new dependency and a spec change. Both are
off limits. Mirroring annotations onto the guest hits the same wall, so
annotation stayed admin-side.

### What changed, and what deliberately did not

Added to: `protocol.py` (2 constants), `screen.py` (`list_monitors()`,
`ScreenGrabber.set_monitor()`), `session.py` (`current_monitor`,
`list_monitors()`, `switch_monitor()`), `connection.py` (`_MONITOR_ACTIONS`,
`_handle_monitors()`, one dispatch branch beside the existing input/term/fs
ones), `RemoteViewer.tsx` (toolbar buttons, handlers, overlay canvas).

**`rmm-server/` needed no change at all.** `_handle_admin_message` already
forwards any action verbatim and `_handle_agent_message` already relays any
`agent_event`, so the new messages pass through untouched. New `mtype` values
would have been dropped, which is why the replies ride `agent_event`.

Untouched and hash-verified after the work: `enroll.py`, `config.py`,
`singleton.py`, `presence.py`, `rmm-agent.spec`, `requirements.txt`,
`ws/handlers.py`, `ws/manager.py`, `build-agent.yml`.

### Verification

- `tests_e2e.py`: **ALL AGENT TESTS PASSED** — connect, hello, 25 heartbeats,
  12 frames, session start/stop, input applied, reconnect after drop.
- Protected files: `md5sum -c` → all 9 **OK**.
- Source diff is additive: 4 removed lines total, each an import or set
  re-added extended in place. No logic replaced.
- Console typecheck and build clean → `index-swc_3zeu.js`.

### Known limitation

The `monitor` field in each frame still reports `config.monitor_index`, not the
switched display — `_stream_loop` is existing code and was left alone. The
console tracks the selection itself, so nothing depends on it.

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
