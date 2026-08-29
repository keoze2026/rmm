"""Privacy blank: a fullscreen black window on the guest during a session.

Self-contained and lazy: tkinter is imported only when blanking is actually
requested, so a headless box (CI, a build server) never touches it and the
rest of the agent stays importable without a display.

The window runs on its own thread with its own tkinter mainloop, so it never
blocks the asyncio event loop or the capture/heartbeat tasks. It does NOT touch
the tray icon — the agent stays visible, by design.

On Windows the window sets WDA_EXCLUDEFROMCAPTURE once: visible to the person
at the machine, excluded from screen capture, so the admin sees and controls
the real desktop behind it. The flag is applied a SINGLE time — reapplying it
on a timer crashed tcl86t.dll. It stays effective because the capture backend
is Windows.Graphics.Capture (see capture_win.py), which honours the exclusion
persistently and keeps delivering live frames; mss/BitBlt did not, which is
what made the admin view go stale.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("agent.blanker")


class Blanker:
    """Owns at most one black fullscreen window, toggled on and off."""

    def __init__(self, message: str = "") -> None:
        self._message = message
        self._thread: threading.Thread | None = None
        self._root = None
        self._on = False

    @property
    def active(self) -> bool:
        return self._on

    def start(self) -> bool:
        """Show the black window. Returns True if it is (or already was) up."""
        if self._on:
            return True
        try:
            import tkinter  # noqa: F401  (probe: fail fast if Tk is missing)
        except Exception as exc:  # pragma: no cover - platform dependent
            log.warning("blank unavailable: tkinter missing (%s)", exc)
            return False

        ready = threading.Event()
        ok = {"v": False}

        def _run() -> None:
            import sys
            import tkinter as tk

            try:
                root = tk.Tk()
                root.configure(bg="black")
                root.attributes("-fullscreen", True)
                root.attributes("-topmost", True)
                root.overrideredirect(True)
                root.config(cursor="none")
                if self._message:
                    tk.Label(
                        root, text=self._message, fg="#888888", bg="black",
                        font=("Arial", 20),
                    ).pack(expand=True)

                # Windows: exclude the window from screen capture ONCE. Applied
                # a single time on purpose — a reapply timer crashed tcl86t.dll.
                # WGC capture (capture_win.py) keeps the exclusion live.
                if sys.platform.startswith("win"):
                    try:
                        import ctypes
                        root.update_idletasks()
                        WDA_EXCLUDEFROMCAPTURE = 0x00000011
                        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                        if not hwnd:
                            hwnd = root.winfo_id()
                        ctypes.windll.user32.SetWindowDisplayAffinity(
                            hwnd, WDA_EXCLUDEFROMCAPTURE)
                    except Exception as exc:  # pragma: no cover - Windows only
                        log.warning("exclude-from-capture failed: %s", exc)

                self._root = root
                ok["v"] = True
                ready.set()
                root.mainloop()
            except Exception as exc:  # pragma: no cover - platform dependent
                log.warning("blank window failed: %s", exc)
                ready.set()

        self._thread = threading.Thread(target=_run, daemon=True, name="blanker")
        self._thread.start()
        ready.wait(timeout=5)
        self._on = ok["v"]
        return self._on

    def stop(self) -> None:
        """Remove the black window. Safe to call when already off."""
        root = self._root
        self._root = None
        self._on = False
        if root is not None:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass
        self._thread = None
