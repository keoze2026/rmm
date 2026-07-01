"""Collect the inventory the server stores per machine.

Maps to the Machine model columns in the Phase 1 server:
hostname, os_name, os_version, os_username, cpu_model, cpu_cores,
ram_total_mb, agent_version.
"""
from __future__ import annotations

import getpass
import platform
import socket

from agent import __version__


def _cpu_model() -> str | None:
    # platform.processor() is empty on many Linux/mac setups; fall back sanely.
    proc = platform.processor()
    if proc:
        return proc
    try:
        if platform.system() == "Linux":
            with open("/proc/cpuinfo", "r", encoding="utf-8") as fh:
                for line in fh:
                    if line.lower().startswith("model name"):
                        return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.machine() or None


def _cpu_cores() -> int | None:
    try:
        import psutil
        return psutil.cpu_count(logical=True)
    except Exception:
        import os
        return os.cpu_count()


def _ram_total_mb() -> int | None:
    try:
        import psutil
        return int(psutil.virtual_memory().total // (1024 * 1024))
    except Exception:
        return None


def _os_name() -> str:
    # Normalise to the values the server expects: windows / darwin / linux.
    return platform.system().lower()


def collect() -> dict:
    """Build the inventory dict sent in the `hello` message."""
    return {
        "hostname": socket.gethostname(),
        "os_name": _os_name(),
        "os_version": platform.platform(),
        "os_username": _safe_username(),
        "cpu_model": _cpu_model(),
        "cpu_cores": _cpu_cores(),
        "ram_total_mb": _ram_total_mb(),
        "agent_version": __version__,
    }


def _safe_username() -> str | None:
    try:
        return getpass.getuser()
    except Exception:
        return None
