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
import logging
import sys
from dataclasses import dataclass

log = logging.getLogger("agent.screen")


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
        self._prev = None   # previous frame, for tile diffing
        self._wgc = None    # Windows.Graphics.Capture source, when available

    def start(self) -> None:
        import mss  # imported lazily; needs a display, real machines only
        self._sct = mss.mss()
        mons = self._sct.monitors
        idx = self.monitor_index if self.monitor_index < len(mons) else 0
        mon = mons[idx]
        self._geometry = (mon["width"], mon["height"])
        self._maybe_start_wgc()

    def _maybe_start_wgc(self) -> None:
        """On Windows, prefer Windows.Graphics.Capture so the privacy-blank
        window's capture-exclusion coexists with live capture. mss stays as the
        fallback if the backend is missing or fails."""
        if not sys.platform.startswith("win"):
            return
        try:
            from agent.capture_win import WGCSource
            wgc = WGCSource(self.monitor_index)
            if wgc.start(timeout=5.0):
                self._wgc = wgc
                g = wgc.geometry()
                if g:
                    self._geometry = g
                log.info("screen capture: using Windows.Graphics.Capture")
            else:
                wgc.stop()
                log.warning("WGC produced no frame in time; using mss")
        except Exception as exc:
            log.warning("WGC unavailable, using mss: %s", exc)

    def _grab_raw_pil(self):
        """Return the current frame as a PIL RGB Image.

        Uses the WGC source when active (composition-aware, survives capture
        exclusion); otherwise mss. One place, so grab() and grab_tiles() share it.
        """
        from PIL import Image
        if self._wgc is not None:
            pil = self._wgc.latest_pil()
            if pil is not None:
                return pil
            # Not ready yet this tick — fall through to mss for one frame.
        mons = self._sct.monitors
        idx = self.monitor_index if self.monitor_index < len(mons) else 0
        shot = self._sct.grab(mons[idx])
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    @property
    def geometry(self) -> tuple[int, int] | None:
        return self._geometry

    def grab(self) -> EncodedFrame:
        if self._sct is None:
            raise RuntimeError("ScreenGrabber.start() must be called first")
        img = self._grab_raw_pil()
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
        # WGC binds a monitor at start, so restart it on the new display.
        if self._wgc is not None:
            try:
                self._wgc.stop()
            except Exception:
                pass
            self._wgc = None
            self._maybe_start_wgc()
        return self._geometry

    def grab_tiles(self, *, cols: int = 8, rows: int = 6, keyframe: bool = False) -> dict:
        """Grab a frame and encode only the tiles that changed.

        A desktop at rest changes almost nothing between frames, so this sends
        a fraction of the bytes a full JPEG costs. Returns a dict with the
        changed tiles and the frame geometry; an empty tile list means nothing
        moved and there is nothing to send.
        """
        if self._sct is None:
            raise RuntimeError("ScreenGrabber.start() must be called first")
        import io as _io
        import base64 as _b64
        from PIL import Image

        img = self._grab_raw_pil()

        if self.max_width and img.size[0] > self.max_width:
            scale = self.max_width / float(img.size[0])
            img = img.resize((self.max_width, max(1, int(img.size[1] * scale))), Image.BILINEAR)

        w, h = img.size
        prev = self._prev
        if prev is None or prev.size != img.size:
            keyframe = True

        tile_w = max(1, w // cols)
        tile_h = max(1, h // rows)
        tiles = []
        for ty in range(rows):
            for tx in range(cols):
                x0, y0 = tx * tile_w, ty * tile_h
                x1 = w if tx == cols - 1 else x0 + tile_w
                y1 = h if ty == rows - 1 else y0 + tile_h
                box = (x0, y0, x1, y1)
                cur = img.crop(box)
                if not keyframe and prev.crop(box).tobytes() == cur.tobytes():
                    continue
                buf = _io.BytesIO()
                cur.save(buf, format="JPEG", quality=int(self.quality), optimize=False)
                tiles.append({
                    "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0,
                    "data": _b64.b64encode(buf.getvalue()).decode("ascii"),
                })

        self._prev = img
        return {"tiles": tiles, "width": w, "height": h, "keyframe": keyframe}

    def close(self) -> None:
        if self._wgc is not None:
            try:
                self._wgc.stop()
            except Exception:
                pass
            self._wgc = None
        if self._sct is not None:
            try:
                self._sct.close()
            except Exception:
                pass
            self._sct = None
