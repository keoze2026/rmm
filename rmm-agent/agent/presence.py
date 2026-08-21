"""Visible presence: tray icon and session notifications.

This is the agent's consent surface. The tray icon is always shown while the
agent runs and reflects connection/session status; an OS notification fires
when a remote session starts (and stops). On a headless box (no display, e.g.
CI or a build server) the real tray backend is unavailable, so we fall back to
a logging implementation that keeps the rest of the agent runnable and
testable. The fallback is for development only — on real Windows/Mac endpoints
the tray icon is present.
"""
from __future__ import annotations

import logging
import os
import sys
import threading

log = logging.getLogger("agent.presence")

# status -> RGB colour for the tray dot
_STATUS_COLORS = {
    "connecting": (240, 180, 0),    # amber
    "online": (40, 170, 90),        # green
    "in_session": (40, 120, 220),   # blue
    "offline": (150, 150, 150),     # grey
}


class Presence:
    """Interface the rest of the agent talks to."""

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def set_status(self, status: str, detail: str = "") -> None: ...
    def notify(self, title: str, message: str) -> None: ...


class NullPresence(Presence):
    """No-op/logging presence for headless environments."""

    def start(self) -> None:
        log.info("presence: running without a tray icon (headless)")

    def stop(self) -> None:
        pass

    def set_status(self, status: str, detail: str = "") -> None:
        log.info("presence status -> %s %s", status, detail)

    def notify(self, title: str, message: str) -> None:
        log.info("presence notify: %s — %s", title, message)


class TrayPresence(Presence):
    """Real tray icon backed by pystray. Runs the icon loop on its own thread."""

    def __init__(self, app_name: str = "Remote Support Agent") -> None:
        self.app_name = app_name
        self._icon = None
        self._thread: threading.Thread | None = None
        self._status = "connecting"
        self._detail = ""

    def _make_image(self, status: str):
        """The broadcast mark as a real tray icon.

        A shape on transparency, not a filled tile: trays render at 16-22px,
        where a full-bleed square reads as a coloured box and thin strokes
        disappear entirely. The glyph fills the canvas with strokes heavy
        enough to survive that downscale, outlined in dark so it stays legible
        on light tray backgrounds as well as dark ones.

        Drawn rather than bundled: a one-file PyInstaller build has no
        dependable asset path at runtime, and pystray takes a PIL image
        directly on Windows, macOS and Linux alike.
        """
        from PIL import Image, ImageDraw

        white = (255, 255, 255, 255)
        edge = (17, 24, 39, 190)          # dark halo for light-coloured trays
        color = _STATUS_COLORS.get(status, _STATUS_COLORS["offline"]) + (255,)

        size = 128
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Three concentric arcs + dot, spanning nearly the whole canvas.
        arcs = ((4, 10, 124, 130), (26, 32, 102, 108), (48, 54, 80, 86))
        for box in arcs:                      # dark halo first
            d.arc(box, start=200, end=340, fill=edge, width=26)
        d.ellipse((50, 86, 78, 114), fill=edge)
        for box in arcs:                      # white glyph on top
            d.arc(box, start=200, end=340, fill=white, width=18)
        d.ellipse((54, 90, 74, 110), fill=white)

        # Status dot, bottom-right, ringed so it reads on any background.
        d.ellipse((84, 84, 126, 126), fill=edge)
        d.ellipse((88, 88, 122, 122), fill=color)
        return img

    def _menu(self):
        import pystray
        return pystray.Menu(
            pystray.MenuItem(lambda item: f"Status: {self._status}", None, enabled=False),
            pystray.MenuItem(lambda item: self._detail or self.app_name, None, enabled=False),
        )

    def start(self) -> None:
        # Prefer AppIndicator/StatusNotifier on Linux. Without this pystray can
        # fall back to its X11 backend, which paints a flat rectangle instead
        # of the icon — the "coloured box" in the tray.
        if sys.platform.startswith("linux") and not os.environ.get("PYSTRAY_BACKEND"):
            for backend in ("appindicator", "gtk", "ayatana-appindicator"):
                try:
                    __import__(f"pystray._{backend.replace('-', '_')}")
                    os.environ["PYSTRAY_BACKEND"] = backend
                    break
                except Exception:
                    continue

        try:
            import pystray  # noqa: F401
        except Exception as exc:  # pragma: no cover - depends on platform
            raise RuntimeError(f"pystray unavailable: {exc}") from exc
        import pystray
        self._icon = pystray.Icon(
            "rmm-agent",
            icon=self._make_image(self._status),
            title=self.app_name,
            menu=self._menu(),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()
        log.info("presence: tray icon started")

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass

    def set_status(self, status: str, detail: str = "") -> None:
        self._status = status
        self._detail = detail
        if self._icon is not None:
            try:
                self._icon.icon = self._make_image(status)
                self._icon.title = f"{self.app_name} — {status}"
                self._icon.update_menu()
            except Exception:
                pass

    def notify(self, title: str, message: str) -> None:
        # Prefer the tray's native notification; fall back to plyer if present.
        if self._icon is not None:
            try:
                self._icon.notify(message, title)
                return
            except Exception:
                pass
        try:  # pragma: no cover - optional dependency
            from plyer import notification
            notification.notify(title=title, message=message, app_name=self.app_name)
        except Exception:
            log.info("notify: %s — %s", title, message)


def build_presence(enabled: bool, app_name: str = "Remote Support Agent") -> Presence:
    """Return a TrayPresence if possible, else a NullPresence."""
    if not enabled:
        return NullPresence()
    try:
        p = TrayPresence(app_name)
        p.start()
        return p
    except Exception as exc:
        log.warning("falling back to headless presence: %s", exc)
        return NullPresence()
