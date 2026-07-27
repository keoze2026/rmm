"""Single-instance guard.

Only ONE agent runs per machine. First to start wins; later starts exit
quietly. If a previous holder died without cleaning up (kill -9, crash,
reboot), its lock is stale and the next start reclaims it instead of being
blocked forever.
"""
from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path


def machine_wide_dir() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "RMAgent"
    elif sys.platform == "darwin":
        base = Path("/Library/Application Support/RMAgent")
    else:
        base = Path("/var/lib/rmagent")
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except OSError:
        return Path(tempfile.gettempdir())


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if sys.platform.startswith("win"):
            import ctypes
            PROCESS_QUERY = 0x1000
            h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY, False, pid)
            if not h:
                return False
            ctypes.windll.kernel32.CloseHandle(h)
            return True
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


class SingleInstance:
    def __init__(self, name: str = "rmm-agent") -> None:
        self._path = machine_wide_dir() / f"{name}.lock"
        self._handle = None

    def acquire(self) -> bool:
        # If a lock file exists but its PID is dead, remove it (stale).
        try:
            if self._path.exists():
                txt = self._path.read_text(encoding="utf-8").strip()
                pid = int(txt) if txt.isdigit() else -1
                if not _pid_alive(pid):
                    self._path.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            if sys.platform.startswith("win"):
                return self._acquire_windows()
            return self._acquire_posix()
        except OSError:
            return True

    def _acquire_posix(self) -> bool:
        import fcntl
        self._handle = open(self._path, "w")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._handle.close()
            self._handle = None
            return False
        self._handle.write(str(os.getpid()))
        self._handle.flush()
        atexit.register(self.release)
        return True

    def _acquire_windows(self) -> bool:  # pragma: no cover - Windows only
        import msvcrt
        self._handle = open(self._path, "a+")
        try:
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._handle.close()
            self._handle = None
            return False
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()
        atexit.register(self.release)
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if sys.platform.startswith("win"):  # pragma: no cover
                import msvcrt
                self._handle.seek(0)
                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._handle.close()
            self._handle = None
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            pass
