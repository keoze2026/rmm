# """Privacy blank: a fullscreen black window on the guest during a session.

# Self-contained and lazy: tkinter is imported only when blanking is actually
# requested, so a headless box (CI, a build server) never touches it and the
# rest of the agent stays importable without a display.

# The window runs on its own thread with its own tkinter mainloop, so it never
# blocks the asyncio event loop or the capture/heartbeat tasks. It does NOT
# touch the tray icon — the agent stays visible, by design.

# Best-effort by nature: this is a userland always-on-top window, not a secure
# desktop. It hides the screen from a casual onlooker; it is not a guarantee the
# local user cannot get past it.
# """
# from __future__ import annotations

# import logging
# import threading

# log = logging.getLogger("agent.blanker")


# class Blanker:
#     """Owns at most one black fullscreen window, toggled on and off."""

#     def __init__(self, message: str = "") -> None:
#         self._message = message
#         self._thread: threading.Thread | None = None
#         self._root = None
#         self._on = False

#     @property
#     def active(self) -> bool:
#         return self._on

#     def start(self) -> bool:
#         """Show the black window. Returns True if it is (or already was) up."""
#         if self._on:
#             return True
#         try:
#             import tkinter  # noqa: F401  (probe: fail fast if Tk is missing)
#         except Exception as exc:  # pragma: no cover - platform dependent
#             log.warning("blank unavailable: tkinter missing (%s)", exc)
#             return False

#         ready = threading.Event()
#         ok = {"v": False}

#         def _run() -> None:
#             import tkinter as tk

#             try:
#                 root = tk.Tk()
#                 root.configure(bg="black")
#                 root.attributes("-fullscreen", True)
#                 root.attributes("-topmost", True)
#                 root.overrideredirect(True)
#                 root.config(cursor="none")
#                 if self._message:
#                     tk.Label(
#                         root, text=self._message, fg="#888888", bg="black",
#                         font=("Arial", 20),
#                     ).pack(expand=True)
#                 # Keep it in front if focus is stolen.
#                 def _reassert() -> None:
#                     try:
#                         root.attributes("-topmost", True)
#                         root.after(1000, _reassert)
#                     except Exception:
#                         pass
#                 root.after(1000, _reassert)
#                 # Windows: make the black window visible to the user but
#                 # INVISIBLE to screen capture, so the guest sees black while the
#                 # admin's capture shows the real desktop behind it. This is the
#                 # actual "privacy screen" behaviour. Needs Windows 10 2004+.
#                 # import sys as _sys
#                 # if _sys.platform.startswith("win"):
#                 #     try:
#                 #         import ctypes
#                 #         root.update_idletasks()
#                 #         WDA_EXCLUDEFROMCAPTURE = 0x00000011
#                 #         hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
#                 #         if not hwnd:
#                 #             hwnd = root.winfo_id()
#                 #         ctypes.windll.user32.SetWindowDisplayAffinity(
#                 #             hwnd, WDA_EXCLUDEFROMCAPTURE)
#                 #     except Exception as exc:  # pragma: no cover - Windows only
#                 #         log.warning("exclude-from-capture failed: %s", exc)

#                 import sys as _sys
#                 if _sys.platform.startswith("win"):
#                     try:
#                         import ctypes
#                         root.update_idletasks()
#                         WDA_EXCLUDEFROMCAPTURE = 0x00000011
#                         hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
#                         if not hwnd:
#                             hwnd = root.winfo_id()

#                         def _reapply_affinity() -> None:
#                             try:
#                                 ctypes.windll.user32.SetWindowDisplayAffinity(
#                                     hwnd, WDA_EXCLUDEFROMCAPTURE)
#                                 root.after(1000, _reapply_affinity)
#                             except Exception:
#                                 pass

#                         ctypes.windll.user32.SetWindowDisplayAffinity(
#                             hwnd, WDA_EXCLUDEFROMCAPTURE)
#                         root.after(1000, _reapply_affinity)
#                     except Exception as exc:  # pragma: no cover - Windows only
#                         log.warning("exclude-from-capture failed: %s", exc)


#                 self._root = root
#                 ok["v"] = True
#                 ready.set()
#                 root.mainloop()
#             except Exception as exc:  # pragma: no cover - platform dependent
#                 log.warning("blank window failed: %s", exc)
#                 ready.set()

#         self._thread = threading.Thread(target=_run, daemon=True, name="blanker")
#         self._thread.start()
#         ready.wait(timeout=5)
#         self._on = ok["v"]
#         return self._on

#     def stop(self) -> None:
#         """Remove the black window. Safe to call when already off."""
#         root = self._root
#         self._root = None
#         self._on = False
#         if root is not None:
#             try:
#                 root.after(0, root.destroy)
#             except Exception:
#                 pass
#         self._thread = None"""Privacy blank: a fullscreen black window on the guest during a session.

# Self-contained and lazy: tkinter is imported only when blanking is actually
# requested, so a headless box (CI, a build server) never touches it and the
# rest of the agent stays importable without a display.

# The window runs on its own thread with its own tkinter mainloop, so it never
# blocks the asyncio event loop or the capture/heartbeat tasks. It does NOT
# touch the tray icon — the agent stays visible, by design.

# Best-effort by nature: this is a userland always-on-top window, not a secure
# desktop. It hides the screen from a casual onlooker; it is not a guarantee the
# local user cannot get past it.
# """
# from __future__ import annotations

# import logging
# import threading

# log = logging.getLogger("agent.blanker")


# class Blanker:
#     """Owns at most one black fullscreen window, toggled on and off."""

#     def __init__(self, message: str = "") -> None:
#         self._message = message
#         self._thread: threading.Thread | None = None
#         self._root = None
#         self._on = False

#     @property
#     def active(self) -> bool:
#         return self._on

#     def start(self) -> bool:
#         """Show the black window. Returns True if it is (or already was) up."""
#         if self._on:
#             return True
#         try:
#             import tkinter  # noqa: F401  (probe: fail fast if Tk is missing)
#         except Exception as exc:  # pragma: no cover - platform dependent
#             log.warning("blank unavailable: tkinter missing (%s)", exc)
#             return False

#         ready = threading.Event()
#         ok = {"v": False}

#         def _run() -> None:
#             import tkinter as tk

#             try:
#                 root = tk.Tk()
#                 root.configure(bg="black")
#                 root.attributes("-fullscreen", True)
#                 root.attributes("-topmost", True)
#                 root.overrideredirect(True)
#                 root.config(cursor="none")
#                 if self._message:
#                     tk.Label(
#                         root, text=self._message, fg="#888888", bg="black",
#                         font=("Arial", 20),
#                     ).pack(expand=True)
#                 # Keep it in front if focus is stolen.
#                 def _reassert() -> None:
#                     try:
#                         root.attributes("-topmost", True)
#                         root.after(1000, _reassert)
#                     except Exception:
#                         pass
#                 root.after(1000, _reassert)
#                 # Windows: make the black window visible to the user but
#                 # INVISIBLE to screen capture, so the guest sees black while the
#                 # admin's capture shows the real desktop behind it. This is the
#                 # actual "privacy screen" behaviour. Needs Windows 10 2004+.
#                 # import sys as _sys
#                 # if _sys.platform.startswith("win"):
#                 #     try:
#                 #         import ctypes
#                 #         root.update_idletasks()
#                 #         WDA_EXCLUDEFROMCAPTURE = 0x00000011
#                 #         hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
#                 #         if not hwnd:
#                 #             hwnd = root.winfo_id()
#                 #         ctypes.windll.user32.SetWindowDisplayAffinity(
#                 #             hwnd, WDA_EXCLUDEFROMCAPTURE)
#                 #     except Exception as exc:  # pragma: no cover - Windows only
#                 #         log.warning("exclude-from-capture failed: %s", exc)

#                 import sys as _sys
#                 if _sys.platform.startswith("win"):
#                     try:
#                         import ctypes
#                         root.update_idletasks()
#                         WDA_EXCLUDEFROMCAPTURE = 0x00000011
#                         hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
#                         if not hwnd:
#                             hwnd = root.winfo_id()

#                         def _reapply_affinity() -> None:
#                             try:
#                                 ctypes.windll.user32.SetWindowDisplayAffinity(
#                                     hwnd, WDA_EXCLUDEFROMCAPTURE)
#                                 root.after(1000, _reapply_affinity)
#                             except Exception:
#                                 pass

#                         ctypes.windll.user32.SetWindowDisplayAffinity(
#                             hwnd, WDA_EXCLUDEFROMCAPTURE)
#                         root.after(1000, _reapply_affinity)
#                     except Exception as exc:  # pragma: no cover - Windows only
#                         log.warning("exclude-from-capture failed: %s", exc)


#                 self._root = root
#                 ok["v"] = True
#                 ready.set()
#                 root.mainloop()
#             except Exception as exc:  # pragma: no cover - platform dependent
#                 log.warning("blank window failed: %s", exc)
#                 ready.set()

#         self._thread = threading.Thread(target=_run, daemon=True, name="blanker")
#         self._thread.start()
#         ready.wait(timeout=5)
#         self._on = ok["v"]
#         return self._on

#     def stop(self) -> None:
#         """Remove the black window. Safe to call when already off."""
#         root = self._root
#         self._root = None
#         self._on = False
#         if root is not None:
#             try:
#                 root.after(0, root.destroy)
#             except Exception:
#                 pass
#         self._thread = None


"""Privacy blank: a fullscreen black window on the guest during a session."""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("agent.blanker")


class Blanker:
    def __init__(self, message: str = "") -> None:
        self._message = message
        self._thread: threading.Thread | None = None
        self._root = None
        self._on = False

    @property
    def active(self) -> bool:
        return self._on

    def start(self) -> bool:
        if self._on:
            return True
        try:
            import tkinter  # noqa: F401
        except Exception as exc:
            log.warning("blank unavailable: tkinter missing (%s)", exc)
            return False

        ready = threading.Event()
        ok = {"v": False}

        def _run() -> None:
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

                def _reassert() -> None:
                    try:
                        root.attributes("-topmost", True)
                        root.after(1000, _reassert)
                    except Exception:
                        pass
                root.after(1000, _reassert)

                import sys as _sys
                if _sys.platform.startswith("win"):
                    try:
                        import ctypes
                        root.update_idletasks()
                        WDA_EXCLUDEFROMCAPTURE = 0x00000011
                        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                        if not hwnd:
                            hwnd = root.winfo_id()
                        ctypes.windll.user32.SetWindowDisplayAffinity(
                            hwnd, WDA_EXCLUDEFROMCAPTURE)
                    except Exception as exc:
                        log.warning("exclude-from-capture failed: %s", exc)

                self._root = root
                ok["v"] = True
                ready.set()
                root.mainloop()
            except Exception as exc:
                log.warning("blank window failed: %s", exc)
                ready.set()

        self._thread = threading.Thread(target=_run, daemon=True, name="blanker")
        self._thread.start()
        ready.wait(timeout=5)
        self._on = ok["v"]
        return self._on

    def stop(self) -> None:
        root = self._root
        self._root = None
        self._on = False
        if root is not None:
            try:
                root.after(0, root.destroy)
            except Exception:
                pass
        self._thread = None
