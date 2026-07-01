"""Remote terminal.

A terminal session spawns the OS shell and streams its output back to the
admin. On POSIX it uses a real PTY (so interactive programs and colors work);
on Windows it falls back to a piped subprocess running cmd.exe.

Like screen capture and input injection, a terminal only runs while a remote
session is ACTIVE — the same session that notified the user. When the session
ends, the shell is killed. Every terminal start/stop is reported as an event so
it lands in the server's activity log.
"""
from __future__ import annotations

import asyncio
import base64
import os
import signal
import sys
from typing import Awaitable, Callable

OutputFn = Callable[[str, str], Awaitable[None]]  # (term_id, base64_data)


class TerminalSession:
    """One shell process bound to a terminal id."""

    def __init__(self, term_id: str, on_output: OutputFn) -> None:
        self.term_id = term_id
        self._on_output = on_output
        self._proc: asyncio.subprocess.Process | None = None
        self._master_fd: int | None = None
        self._reader_task: asyncio.Task | None = None
        self._loop = asyncio.get_event_loop()
        self._alive = False

    async def start(self, cols: int = 80, rows: int = 24) -> None:
        if sys.platform.startswith("win"):
            await self._start_windows()
        else:
            await self._start_posix(cols, rows)
        self._alive = True

    # --- POSIX (real PTY) --------------------------------------------------
    async def _start_posix(self, cols: int, rows: int) -> None:
        import pty
        import fcntl
        import termios
        import struct

        master, slave = pty.openpty()
        # Best-effort initial window size.
        try:
            fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

        shell = os.environ.get("SHELL", "/bin/bash")
        self._proc = await asyncio.create_subprocess_exec(
            shell,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            start_new_session=True,
            env={**os.environ, "TERM": "xterm-256color"},
        )
        os.close(slave)
        self._master_fd = master
        os.set_blocking(master, False)
        self._reader_task = asyncio.create_task(self._read_posix())

    async def _read_posix(self) -> None:
        assert self._master_fd is not None
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[bytes | None] = asyncio.Queue()

        def _on_readable() -> None:
            try:
                data = os.read(self._master_fd, 65536)
            except (OSError, BlockingIOError):
                return
            loop.call_soon_threadsafe(queue.put_nowait, data or None)

        loop.add_reader(self._master_fd, _on_readable)
        try:
            while True:
                data = await queue.get()
                if data is None:
                    break
                await self._on_output(self.term_id, base64.b64encode(data).decode("ascii"))
        finally:
            try:
                loop.remove_reader(self._master_fd)
            except (OSError, ValueError):
                pass

    # --- Windows (piped cmd.exe) ------------------------------------------
    async def _start_windows(self) -> None:  # pragma: no cover - Windows only
        self._proc = await asyncio.create_subprocess_exec(
            "cmd.exe",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._reader_task = asyncio.create_task(self._read_windows())

    async def _read_windows(self) -> None:  # pragma: no cover - Windows only
        assert self._proc and self._proc.stdout
        while True:
            data = await self._proc.stdout.read(65536)
            if not data:
                break
            await self._on_output(self.term_id, base64.b64encode(data).decode("ascii"))

    # --- input / control ---------------------------------------------------
    async def write(self, data: str) -> None:
        raw = data.encode("utf-8", "replace")
        if self._master_fd is not None:
            try:
                os.write(self._master_fd, raw)
            except OSError:
                pass
        elif self._proc and self._proc.stdin:  # pragma: no cover - Windows only
            self._proc.stdin.write(raw)

    def resize(self, cols: int, rows: int) -> None:
        if self._master_fd is None:
            return
        try:
            import fcntl
            import termios
            import struct
            fcntl.ioctl(self._master_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except OSError:
            pass

    async def stop(self) -> None:
        self._alive = False
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
        if self._proc and self._proc.returncode is None:
            try:
                if sys.platform.startswith("win"):  # pragma: no cover
                    self._proc.terminate()
                else:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
            except (ProcessLookupError, OSError):
                pass
        if self._master_fd is not None:
            try:
                os.close(self._master_fd)
            except OSError:
                pass
            self._master_fd = None