# RMM Server — Phase 1 (FastAPI + WebSocket Backend)

Self-hosted Remote Monitoring & Management server. Phase 1 covers the
**database, authentication, REST API, and WebSocket handler**.

> Agent model is **consent-aware**: machines run a visible agent (tray icon +
> session-start notification), there is **no global keystroke logging**, and
> every connect/session/command is written to an audit log.

## Stack
FastAPI · Uvicorn · SQLAlchemy 2 (async) · PostgreSQL (asyncpg) · Redis ·
PyJWT · bcrypt · WebSockets. Runs on port **8765**.

## What's in this phase
- Admin auth: register, login (JWT), `/me`
- Machines: enroll (unique one-time agent token), list, get, update, delete, regenerate token
- Sessions + activity/audit log (read APIs)
- WebSocket endpoints: `/ws/agent` (token auth), `/ws/admin` (JWT auth)
- Online-state tracking via Redis, cross-worker command/event routing via pub/sub
- Heartbeat + stale-agent offline reaper

---

## Setup (Parrot OS / Linux)

### 1. PostgreSQL database + user
```bash
sudo -u postgres psql -c "CREATE USER rmm WITH PASSWORD 'rmm';"
sudo -u postgres psql -c "CREATE DATABASE rmm OWNER rmm;"
```

### 2. Redis (you already have 8.0.2) — confirm it's up
```bash
redis-cli ping        # expect: PONG
```

### 3. Python env + dependencies
```bash
cd rmm-server
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment
```bash
cp .env.example .env
# generate a real JWT secret and paste it into .env (JWT_SECRET=...)
openssl rand -hex 32
```

### 5. Run the server (creates tables on first start)
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
```

Open:
- API docs (Swagger): http://localhost:8765/docs
- Health check:        http://localhost:8765/health

---

## Smoke test (new terminal)

```bash
# 1. Register the first admin (auto-promoted to superadmin)
curl -s -X POST http://localhost:8765/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@keozx.com","password":"supersecret123","full_name":"Keoze"}' | jq

# 2. Login -> grab the access token
TOKEN=$(curl -s -X POST http://localhost:8765/api/auth/login \
  -d 'username=admin@keozx.com&password=supersecret123' | jq -r .access_token)
echo "$TOKEN"

# 3. Enroll a machine -> note the one-time "agent_token" (used by the agent in Phase 2)
curl -s -X POST http://localhost:8765/api/machines \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"DESKTOP-OPS-01"}' | jq

# 4. List machines
curl -s http://localhost:8765/api/machines -H "Authorization: Bearer $TOKEN" | jq

# 5. View the audit log
curl -s http://localhost:8765/api/activity -H "Authorization: Bearer $TOKEN" | jq
```

---

## WebSocket protocol (envelope used across all phases)
Every message is JSON: `{"type": "...", ...}`.

**Agent → server:** `hello` (inventory), `heartbeat`, `frame` (Phase 5), `terminal_output`, `file_chunk`
**Server → agent:** `welcome`, `command` (action + payload), `ping`
**Admin → server:** `subscribe`/`unsubscribe` (per machine), `command` (machine_id + action)
**Server → admin:** `machines_snapshot`, `machine_status`, `machine_inventory`, `frame`, `command_failed`

Agent connects to: `wss://HOST:8765/ws/agent?token=<agent_token>`
Admin connects to: `wss://HOST:8765/ws/admin?token=<jwt>`

> Local dev uses `ws://`. WSS/TLS is terminated at the reverse proxy on the VPS
> (Phase 10 deploy).

---

## Project layout
```
rmm-server/
├── app/
│   ├── main.py            # FastAPI app, lifespan, router wiring, /health
│   ├── config.py          # env-driven settings (pydantic-settings)
│   ├── database.py        # async engine, session, Base, init_db
│   ├── redis_client.py    # redis client + key/channel helpers
│   ├── reaper.py          # stale-agent offline background task
│   ├── models/            # User, Machine, RemoteSession, ActivityLog
│   ├── schemas/           # pydantic request/response models
│   ├── core/              # security (jwt/bcrypt/tokens), deps, audit
│   ├── api/               # auth, machines, sessions REST routers
│   └── ws/                # manager (routing) + handlers (agent/admin WS)
├── requirements.txt
├── .env.example
└── README.md
```

## Next: Phase 2 — the Python agent
Screen capture (mss), WSS client with the envelope above, heartbeat loop,
auto-reconnect, inventory `hello`, and a visible tray icon + session notification.
