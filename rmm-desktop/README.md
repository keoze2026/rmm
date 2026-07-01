# RMM Console — Phase 4 (desktop admin app)

The Electron + React + TypeScript + Tailwind console for monitoring your managed
machines. Phase 4 covers sign-in, the live machine list (real-time online/offline
over the admin WebSocket), search, and enrolling machines (which hands you the
one-time agent token + a ready `config.json`). The remote screen viewer and
mouse/keyboard control come in Phase 5.

## Stack

- **electron-vite** — main / preload / renderer with one config and fast HMR.
- **React 18 + TypeScript + Tailwind 3** for the UI.
- **electron-builder** for installers (AppImage/deb, exe, dmg).

## Layout

```
rmm-desktop/
├── electron.vite.config.ts
├── electron-builder.yml
├── src/
│   ├── main/index.ts        Electron main process (secure window)
│   ├── preload/index.ts     minimal contextBridge surface
│   └── renderer/
│       ├── index.html
│       └── src/
│           ├── App.tsx            Login vs Dashboard
│           ├── auth.tsx           session: server URL + JWT + user
│           ├── api.ts             REST client (login, me, machines, enroll)
│           ├── useMachines.ts     REST seed + admin WS, live updates
│           ├── types.ts
│           ├── pages/             Login, Dashboard
│           └── components/        TopBar, MachineList, StatusDot, AddMachineDialog
```

## Run (dev)

```bash
cd rmm-desktop
npm install
npm run dev          # launches the Electron window with hot reload
```

Sign in with your server URL (default `http://localhost:8765`) and the admin
account you registered on the server. The list goes live immediately: dots flip
as agents connect/disconnect, inventory fills in as agents report it.

> The dev window needs a desktop session. On a headless box only `npm run build`
> (bundle/type check) works, not `npm run dev`.

## How it talks to the server

- `POST /api/auth/login` (form) → JWT, kept in the session.
- `GET /api/machines` seeds the full list once.
- `WS /ws/admin?token=<jwt>` keeps it live: `machines_snapshot`, `machine_status`,
  `machine_inventory`. Reconnects with backoff if the socket drops.
- `POST /api/machines` enrolls a machine and returns the agent token once; the
  Add-machine dialog shows it plus a paste-ready `config.json`.

Same JWT + WSS contract the server already exposes; nothing new is required
server-side.

## Build / package

```bash
npm run build        # type-check + bundle main/preload/renderer into out/
npm run dist:linux   # AppImage + deb   (build on Linux)
npm run dist:win     # exe installer    (build on Windows)
npm run dist:mac     # dmg              (build on macOS)
```

Each OS installer is built on that OS (electron-builder doesn't cross-compile
cleanly). For your Parrot box, `npm run dist:linux` gives an AppImage you can run
directly.
