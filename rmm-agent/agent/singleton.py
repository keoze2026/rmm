"""Single-instance guard.

On shared machines several people may be logged in at once (fast user
switching). Each logged-in session would otherwise start its own agent, and
two agents sharing one machine token would fight over the server connection.
This lock ensures only ONE agent runs per machine: the first to start wins,
later starts exit quietly.

The lock file lives in a machine-wide directory so the lock is visible across
user sessions (not per-user temp). Uses fcntl on POSIX and msvcrt on Windows.
"""
from __future__ import annotations

import atexit
import os
import sys
import tempfile
from pathlib import Path


def machine_wide_dir() -> Path:
    """A directory all users on the machine can reach, for lock + shared config."""
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
        # Fall back to temp if we can't write the machine-wide path (e.g. dev).
        return Path(tempfile.gettempdir())


class SingleInstance:
    def __init__(self, name: str = "rmm-agent") -> None:
        self._path = machine_wide_dir() / f"{name}.lock"
        self._handle = None

    def acquire(self) -> bool:
        """Return True if we got the lock, False if another agent holds it."""
        try:
            if sys.platform.startswith("win"):
                return self._acquire_windows()
            return self._acquire_posix()
        except OSError:
            # If locking itself errors, don't block startup.
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
        atexit.register(self.release)
        return True

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            if sys.platform.startswith("win"):  # pragma: no cover - Windows only
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