"""Agent configuration."""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# def _base_dir() -> Path:
#     if getattr(sys, "frozen", False):
#         meipass = getattr(sys, "_MEIPASS", None)
#         if meipass and (Path(meipass) / "config.json").exists():
#             return Path(meipass)
#         return Path(sys.executable).resolve().parent
#     return Path(__file__).resolve().parent.parent


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if (exe_dir / "config.json").exists():
            return exe_dir
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass and (Path(meipass) / "config.json").exists():
            return Path(meipass)
        return exe_dir
    return Path(__file__).resolve().parent.parent

# Double underscore is a sentinel: it never appears in a platform suffix or a
# product name, so only a filename the download route built can match.
_EXE_CODE_RE = re.compile(r"__([A-Z0-9]{4,12})$")
# Browsers append " (1)", " (2)", … when the same file is downloaded twice.
_DUP_SUFFIX_RE = re.compile(r"\s*\(\d+\)$")


def _match_code(stem: str) -> str:
    """Pull a support code out of one filename stem, or return ""."""
    cleaned = _DUP_SUFFIX_RE.sub("", stem.upper()).strip()
    m = _EXE_CODE_RE.search(cleaned)
    return m.group(1) if m else ""


def _code_from_exe_name() -> str:
    """If the connector was downloaded as rmm-connector__<CODE>.exe, pull <CODE>
    out of the filename so the guest gets a bound session with zero setup.

    The separator is deliberately ``__``. A single dash matched the platform
    suffix as well: ``rmm-connector-windows`` yielded "WINDOWS" and the
    always-on ``rmm-agent`` yielded "AGENT", so every endpoint enrolled with a
    bogus code — which the server silently failed to bind, and which also sent
    the agent down the never-cache-a-token path in ``enroll.ensure_token``.

    Two carriers, same convention:
      * the executable itself   — rmm-connector__RG6092[.exe]  (Windows/Linux)
      * the enclosing .app name — Remote Support Agent__RG6092.app  (macOS,
        where the executable inside the bundle always keeps its build name).
        The bundle *name* is used rather than a file dropped inside Contents/,
        which would invalidate the ad-hoc code signature and stop the app
        launching at all on Apple Silicon.
    """
    try:
        if not getattr(sys, "frozen", False):
            return ""
        exe = Path(sys.executable)
        code = _match_code(exe.stem)
        if code:
            return code
        for parent in exe.parents:
            if parent.suffix.lower() == ".app":
                return _match_code(parent.stem)
    except Exception:
        pass
    return ""

DEFAULT_CONFIG_PATH = _base_dir() / "config.json"


def resolve_config_path() -> Path:
    env = os.environ.get("RMM_CONFIG")
    if env:
        return Path(env)
    candidates = [_base_dir() / "config.json"]
    try:
        from agent.singleton import machine_wide_dir
        candidates.append(machine_wide_dir() / "config.json")
    except Exception:
        pass
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "config.json")
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


@dataclass
class AgentConfig:
    server_url: str = "ws://localhost:8765"
    token: str = ""
    enroll_secret: str = ""
    support_code: str = ""
    heartbeat_interval: float = 10.0
    frame_fps: float = 8.0
    frame_quality: int = 60
    frame_max_width: int = 1600
    monitor_index: int = 1
    reconnect_min: float = 1.0
    reconnect_max: float = 30.0
    tls_insecure: bool = True
    show_tray_icon: bool = True
    notify_on_session: bool = True
    allow_remote_input: bool = True
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "AgentConfig":
        path = path or DEFAULT_CONFIG_PATH
        data: dict = {}
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                print(f"[config] failed to read {path}: {exc}", file=sys.stderr)

        for f in (
            "server_url", "token", "enroll_secret", "support_code",
            "heartbeat_interval", "frame_fps",
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
            support_code=str(data.get("support_code", cls.support_code)) or _code_from_exe_name(),
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
        sep = "&" if "?" in self.server_url else "?"
        base = self.server_url.rstrip("/")
        if not base.endswith("/ws/agent"):
            base = base + "/ws/agent"
        return f"{base}{sep}token={self.token}"

    @property
    def http_base(self) -> str:
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
    "server_url", "token", "enroll_secret", "support_code",
    "heartbeat_interval", "frame_fps", "frame_quality",
    "frame_max_width", "monitor_index", "reconnect_min", "reconnect_max",
    "tls_insecure", "show_tray_icon", "notify_on_session", "allow_remote_input",
}


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
