"""Windows.Graphics.Capture source (Windows only).

Why this exists: mss captures the screen with BitBlt, which returns a stale,
cached frame the moment a window sets ``WDA_EXCLUDEFROMCAPTURE`` (the privacy-
blank window). The tile-diff then sees "nothing changed" and the admin's view
freezes. Windows.Graphics.Capture is composition-aware and honours that
exclusion the way DWM intends: it keeps delivering *live* frames of the desktop
behind the black window. DXGI Desktop Duplication would not help here — it
captures the composed monitor output, which still contains the black window.

This backend runs WGC on its own thread (``start_free_threaded``) and keeps the
latest frame in a buffer; ScreenGrabber reads it on its own cadence. It is
lazily imported and fully optional: if ``windows-capture`` is missing or WGC
fails, ScreenGrabber falls back to mss and nothing here runs.
"""
from __future__ import annotations

import logging
import threading

log = logging.getLogger("agent.capture_win")


class WGCSource:
    """Latest-frame Windows.Graphics.Capture source for one monitor."""

    def __init__(self, monitor_index: int = 1) -> None:
        # WGC monitor_index is 1-based (1 = primary). mss's index 0 ("all
        # monitors") has no WGC equivalent, so clamp to at least 1.
        self._monitor_index = max(1, int(monitor_index))
        self._latest = None            # numpy BGRA array (H, W, 4)
        self._size: tuple[int, int] | None = None
        self._lock = threading.Lock()
        self._control = None
        self._first = threading.Event()

    def start(self, timeout: float = 5.0) -> bool:
        """Begin capture. Returns True once the first frame has arrived."""
        from windows_capture import WindowsCapture  # lazy; Windows only

        cap = WindowsCapture(
            cursor_capture=True,
            draw_border=False,
            monitor_index=self._monitor_index,
            window_name=None,
        )

        @cap.event
        def on_frame_arrived(frame, capture_control):  # noqa: ANN001
            try:
                buf = frame.frame_buffer  # numpy (H, W, 4), BGRA
                with self._lock:
                    self._latest = buf.copy()   # buffer is reused; copy it
                    self._size = (int(frame.width), int(frame.height))
                self._first.set()
            except Exception:
                pass

        @cap.event
        def on_closed():  # noqa: ANN001
            pass

        self._control = cap.start_free_threaded()
        return self._first.wait(timeout)

    def latest_pil(self):
        """Return the newest frame as a PIL RGB Image, or None if not ready."""
        with self._lock:
            buf = self._latest
        if buf is None:
            return None
        import numpy as np
        from PIL import Image
        # BGRA -> RGB, made contiguous for PIL.
        rgb = np.ascontiguousarray(buf[:, :, 2::-1])
        return Image.fromarray(rgb, "RGB")

    def geometry(self) -> tuple[int, int] | None:
        with self._lock:
            return self._size

    def stop(self) -> None:
        ctrl = self._control
        self._control = None
        if ctrl is not None:
            try:
                ctrl.stop()
            except Exception:
                pass
