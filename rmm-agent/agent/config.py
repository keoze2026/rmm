"""Agent configuration.

Config is read from a JSON file (default: config.json next to the executable)
and can be overridden by environment variables prefixed with RMM_. This keeps
the per-machine enrollment token out of source control while staying simple
enough to ship inside a PyInstaller bundle.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _base_dir() -> Path:
    """Directory the agent considers 'home' for its config.

    When frozen by PyInstaller, sys.frozen is set and the executable lives in a
    temp dir, so we anchor config next to the actual .exe/.app, not the bundle.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller extracts bundled data files to sys._MEIPASS. Prefer a
        # config.json bundled INSIDE the binary so the single downloaded file
        # is fully self-contained; fall back to one sitting next to the exe.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / "config.json").exists():
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


DEFAULT_CONFIG_PATH = _base_dir() / "config.json"


def resolve_config_path() -> Path:
    """Pick the config file to use.

    Search order: RMM_CONFIG env var -> config.json next to the executable ->
    the machine-wide dir (shared by all users on a multi-user PC). Falls back to
    the next-to-exe path for first-time writes.
    """
    env = os.environ.get("RMM_CONFIG")
    if env:
        return Path(env)
    candidates = [_base_dir() / "config.json"]
    try:
        from agent.singleton import machine_wide_dir
        candidates.append(machine_wide_dir() / "config.json")
    except Exception:
        pass
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@dataclass
class AgentConfig:
    # wss://host:port  (use ws:// only for local development)
    server_url: str = "ws://localhost:8765"
    # Per-machine enrollment token issued by the server at enroll time.
    token: str = ""
    # Shared enroll secret (baked into installer) for seamless first-run enrollment.
    enroll_secret: str = ""

    # Heartbeat cadence. Server marks offline after AGENT_OFFLINE_AFTER (30s),
    # so 10s gives us three misses of headroom.
    heartbeat_interval: float = 10.0

    # Screen streaming.
    frame_fps: float = 8.0           # frames per second while a session is active
    frame_quality: int = 60          # JPEG quality 1-95
    frame_max_width: int = 1600      # downscale wide screens to cap bandwidth
    monitor_index: int = 1           # mss monitor index (1 = primary)

    # Reconnect backoff (seconds).
    reconnect_min: float = 1.0
    reconnect_max: float = 30.0

    # TLS: allow self-signed certs on the VPS during bring-up. Set false in prod
    # once a real cert is in place.
    tls_insecure: bool = True

    # Visible presence. These default ON and should stay ON; they are the
    # consent surface for the people using the monitored machines.
    show_tray_icon: bool = True
    notify_on_session: bool = True

    # Allow the admin to send input during a session (remote control). If false,
    # the agent streams the screen view-only and ignores input commands.
    allow_remote_input: bool = True

    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "AgentConfig":
        path = path or DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:  # pragma: no cover - defensive
                print(f"[config] failed to read {path}: {exc}", file=sys.stderr)

        # Environment overrides (RMM_SERVER_URL, RMM_TOKEN, ...).
        for f in (
            "server_url", "token", "enroll_secret", "heartbeat_interval", "frame_fps",
            "frame_quality", "frame_max_width", "monitor_index",
            "reconnect_min", "reconnect_max", "tls_insecure",
            "show_tray_icon", "notify_on_session", "allow_remote_input",
        ):
            env = os.environ.get("RMM_" + f.upper())
            if env is not None:
                data[f] = env

        return cls(
            server_url=str(data.get("server_url", cls.server_url)),
            token=str(data.get("token", cls.token)),
            enroll_secret=str(data.get("enroll_secret", cls.enroll_secret)),
            heartbeat_interval=float(data.get("heartbeat_interval", cls.heartbeat_interval)),
            frame_fps=float(data.get("frame_fps", cls.frame_fps)),
            frame_quality=int(data.get("frame_quality", cls.frame_quality)),
            frame_max_width=int(data.get("frame_max_width", cls.frame_max_width)),
            monitor_index=int(data.get("monitor_index", cls.monitor_index)),
            reconnect_min=float(data.get("reconnect_min", cls.reconnect_min)),
            reconnect_max=float(data.get("reconnect_max", cls.reconnect_max)),
            tls_insecure=_as_bool(data.get("tls_insecure", cls.tls_insecure)),
            show_tray_icon=_as_bool(data.get("show_tray_icon", cls.show_tray_icon)),
            notify_on_session=_as_bool(data.get("notify_on_session", cls.notify_on_session)),
            allow_remote_input=_as_bool(data.get("allow_remote_input", cls.allow_remote_input)),
            extra={k: v for k, v in data.items() if k not in _KNOWN_KEYS},
        )

    @property
    def agent_ws_url(self) -> str:
        """Full agent endpoint with the token as a query param."""
        sep = "&" if "?" in self.server_url else "?"
        base = self.server_url.rstrip("/")
        if not base.endswith("/ws/agent"):
            base = base + "/ws/agent"
        return f"{base}{sep}token={self.token}"

    @property
    def http_base(self) -> str:
        """HTTP(S) base URL derived from server_url (for the enroll call)."""
        base = self.server_url.rstrip("/")
        for suf in ("/ws/agent", "/ws/admin", "/ws"):
            if base.endswith(suf):
                base = base[: -len(suf)]
        if base.startswith("wss://"):
            return "https://" + base[len("wss://"):]
        if base.startswith("ws://"):
            return "http://" + base[len("ws://"):]
        return base


_KNOWN_KEYS = {
    "server_url", "token", "enroll_secret", "heartbeat_interval", "frame_fps", "frame_quality",
    "frame_max_width", "monitor_index", "reconnect_min", "reconnect_max",
    "tls_insecure", "show_tray_icon", "notify_on_session", "allow_remote_input",
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}