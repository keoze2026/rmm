"""First-run auto-enrollment.

If the agent has no token but was shipped with an enroll_secret (baked into the
installer), it registers itself with the server on first run, caches the issued
token machine-wide, and reuses it on every subsequent run. The user never
handles a token.
"""
from __future__ import annotations

import json
import platform
import socket
import ssl
import sys
import urllib.request
from pathlib import Path


def _cache_candidates() -> list[Path]:
    """Where to read/write the enrollment token, most-persistent first.

    IMPORTANT: never prefer a temp dir — /tmp is wiped on reboot, which would
    make the agent re-enroll and create a duplicate machine every boot. We put
    persistent per-user locations first and only use the machine-wide dir if it
    is NOT a temp path.
    """
    import tempfile
    paths: list[Path] = []

    # 1) Persistent per-user data dir (always writable, survives reboot).
    paths.append(Path.home() / ".local" / "share" / "rmm" / "agent_token")

    # 2) Next to the frozen executable (persistent, portable installs).
    try:
        if getattr(sys, "frozen", False):
            paths.append(Path(sys.executable).resolve().parent / "agent_token")
    except Exception:
        pass

    # 3) Per-user config dir (persistent).
    paths.append(Path.home() / ".config" / "rmm" / "agent_token")

    # 4) Machine-wide dir — ONLY if it is not a temp path (so multi-user PCs
    #    share one identity), never /tmp.
    try:
        from agent.singleton import machine_wide_dir
        mw = machine_wide_dir()
        tmp = Path(tempfile.gettempdir()).resolve()
        if tmp not in (mw.resolve(), *mw.resolve().parents):
            paths.append(mw / "agent_token")
    except Exception:
        pass

    return paths


def load_cached_token() -> str | None:
    for p in _cache_candidates():
        try:
            if p.exists():
                tok = p.read_text(encoding="utf-8").strip()
                if tok:
                    return tok
        except OSError:
            continue
    return None


def save_cached_token(token: str) -> None:
    for p in _cache_candidates():
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(token, encoding="utf-8")
            return
        except OSError:
            continue


def auto_enroll(config) -> str:
    url = config.http_base.rstrip("/") + "/api/enroll"
    body = json.dumps({
        "enroll_secret": config.enroll_secret,
        "name": socket.gethostname() or "endpoint",
        "hostname": socket.gethostname(),
        "os_name": f"{platform.system()} {platform.release()}".strip(),
    }).encode("utf-8")

    ctx = None
    if url.startswith("https"):
        ctx = ssl.create_default_context()
        if config.tls_insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = data.get("agent_token")
    if not token:
        raise RuntimeError("server did not return a token")
    return token


def ensure_token(config) -> str:
    """Return a usable token: existing -> cached -> freshly enrolled."""
    if config.token:
        return config.token
    cached = load_cached_token()
    if cached:
        return cached
    token = auto_enroll(config)
    save_cached_token(token)
    return token
