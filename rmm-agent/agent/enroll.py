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
    import tempfile
    paths: list[Path] = []
    paths.append(Path.home() / ".local" / "share" / "rmm" / "agent_token")
    try:
        if getattr(sys, "frozen", False):
            paths.append(Path(sys.executable).resolve().parent / "agent_token")
    except Exception:
        pass
    paths.append(Path.home() / ".config" / "rmm" / "agent_token")
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
    payload = {
        "enroll_secret": config.enroll_secret,
        "name": socket.gethostname() or "endpoint",
        "hostname": socket.gethostname(),
        "os_name": f"{platform.system()} {platform.release()}".strip(),
    }
    code = getattr(config, "support_code", None)
    if code:
        payload["support_code"] = code
    body = json.dumps(payload).encode("utf-8")

    ctx = None
    if url.startswith("https"):
        try:
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
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
    if config.token:
        return config.token
    cached = load_cached_token()
    if cached:
        return cached
    token = auto_enroll(config)
    save_cached_token(token)
    return token
