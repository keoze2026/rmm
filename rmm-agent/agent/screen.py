"""Screen capture and frame encoding.

Capture uses `mss` (fast, cross-platform) and encoding uses Pillow to produce
JPEG bytes that are base64-wrapped for the JSON envelope. The encode step is
deliberately split out from capture so it can be unit-tested with a synthetic
image on a headless box (no display required).

Capture only happens while a session is active (see session.py); this module
has no global hooks and never runs on its own.
"""
from __future__ import annotations

import base64
import io
from dataclasses import dataclass


@dataclass
class EncodedFrame:
    data_b64: str
    width: int
    height: int


def encode_frame(image, *, quality: int = 60, max_width: int = 1600) -> EncodedFrame:
    """Encode a Pillow Image to a base64 JPEG, downscaling if wider than max_width.

    `image` is a PIL.Image.Image. Kept Pillow-only so it is testable without a
    real screen.
    """
    from PIL import Image  # local import keeps headless import of this module cheap

    if image.mode not in ("RGB", "L"):
        image = image.convert("RGB")

    w, h = image.size
    if max_width and w > max_width:
        scale = max_width / float(w)
        new_size = (max_width, max(1, int(h * scale)))
        image = image.resize(new_size, Image.BILINEAR)
        w, h = image.size

    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=int(quality), optimize=False)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return EncodedFrame(data_b64=data, width=w, height=h)


def list_monitors() -> list[dict]:
    """Describe the displays mss can see. New function; nothing else uses it.

    Index 0 is mss's virtual "all monitors" rectangle; 1 is the primary. Opens
    its own short-lived mss instance so a live capture session is untouched.
    """
    import mss

    with mss.mss() as sct:
        return [
            {
                "index": i,
                "width": mon["width"],
                "height": mon["height"],
                "left": mon["left"],
                "top": mon["top"],
                "all": i == 0,
                "primary": i == 1,
            }
            for i, mon in enumerate(sct.monitors)
        ]


class ScreenGrabber:
    """Thin wrapper over mss that yields encoded frames for one monitor.

    Holds the mss instance for the life of a session. Construct on session
    start, call `grab()` per frame, and `close()` on session stop.
    """

    def __init__(self, monitor_index: int = 1, *, quality: int = 60,
                 max_width: int = 1600) -> None:
        self.monitor_index = monitor_index
        self.quality = quality
        self.max_width = max_width
        self._sct = None
        self._geometry: tuple[int, int] | None = None

    def start(self) -> None:
        import mss  # imported lazily; needs a display, real machines only
        self._sct = mss.mss()
        mons = self._sct.monitors
        idx = self.monitor_index if self.monitor_index < len(mons) else 0
        mon = mons[idx]
        self._geometry = (mon["width"], mon["height"])

    @property
    def geometry(self) -> tuple[int, int] | None:
        return self._geometry

    def grab(self) -> EncodedFrame:
        if self._sct is None:
            raise RuntimeError("ScreenGrabber.start() must be called first")
        from PIL import Image
        mons = self._sct.monitors
        idx = self.monitor_index if self.monitor_index < len(mons) else 0
        shot = self._sct.grab(mons[idx])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return encode_frame(img, quality=self.quality, max_width=self.max_width)

    def set_monitor(self, index: int) -> tuple[int, int] | None:
        """Point an open grabber at another display.

        New method. grab() already re-reads self.monitor_index on every frame,
        so switching needs nothing more than updating it — no restart, and no
        change to start()/grab()/close().
        """
        if self._sct is None:
            return None
        mons = self._sct.monitors
        idx = index if 0 <= index < len(mons) else 0
        self.monitor_index = idx
        mon = mons[idx]
        self._geometry = (mon["width"], mon["height"])
        return self._geometry

    def close(self) -> None:
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
