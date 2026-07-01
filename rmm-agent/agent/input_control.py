"""Remote input injection.

IMPORTANT: this module only ever *injects* input on behalf of a connected
admin during an active session. It uses pynput's `Controller` classes, which
synthesize events. It does NOT use pynput's `Listener` classes, which would
capture the local user's own keyboard/mouse. There is no keylogging here, by
construction, and adding a Listener to this file would break the agent's
consent model.

Coordinates arrive normalized (0.0-1.0) from the admin viewer so they are
resolution-independent; we scale them to the target screen geometry.
"""
from __future__ import annotations


# Map friendly key names from the admin viewer to pynput special keys.
def _special_keys():
    from pynput.keyboard import Key
    return {
        "enter": Key.enter, "return": Key.enter, "tab": Key.tab,
        "space": Key.space, "backspace": Key.backspace, "delete": Key.delete,
        "esc": Key.esc, "escape": Key.esc, "up": Key.up, "down": Key.down,
        "left": Key.left, "right": Key.right, "home": Key.home, "end": Key.end,
        "pageup": Key.page_up, "pagedown": Key.page_down,
        "shift": Key.shift, "ctrl": Key.ctrl, "control": Key.ctrl,
        "alt": Key.alt, "cmd": Key.cmd, "win": Key.cmd, "super": Key.cmd,
        "capslock": Key.caps_lock, "f1": Key.f1, "f2": Key.f2, "f3": Key.f3,
        "f4": Key.f4, "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
    }


class InputInjector:
    """Applies admin input to the local machine during an active session."""

    def __init__(self, screen_size: tuple[int, int]) -> None:
        self._w, self._h = screen_size
        self._mouse = None
        self._kbd = None
        self._buttons = None
        self._special = None

    def start(self) -> None:
        from pynput.mouse import Controller as MouseController, Button
        from pynput.keyboard import Controller as KeyController
        self._mouse = MouseController()
        self._kbd = KeyController()
        self._buttons = {
            "left": Button.left, "right": Button.right, "middle": Button.middle,
        }
        self._special = _special_keys()

    def set_screen_size(self, size: tuple[int, int]) -> None:
        self._w, self._h = size

    # --- coordinate helpers ------------------------------------------------
    def _to_pixels(self, x: float, y: float) -> tuple[int, int]:
        # Accept either normalized (<=1.0) or absolute pixel coordinates.
        px = int(x * self._w) if 0.0 <= x <= 1.0 else int(x)
        py = int(y * self._h) if 0.0 <= y <= 1.0 else int(y)
        return px, py

    # --- dispatch ----------------------------------------------------------
    def apply(self, action: str, payload: dict) -> None:
        if self._mouse is None or self._kbd is None:
            return
        payload = payload or {}
        handler = _DISPATCH.get(action)
        if handler is not None:
            handler(self, payload)

    # --- mouse -------------------------------------------------------------
    def _mouse_move(self, p: dict) -> None:
        self._mouse.position = self._to_pixels(p.get("x", 0), p.get("y", 0))

    def _mouse_down(self, p: dict) -> None:
        self._mouse.position = self._to_pixels(p.get("x", 0), p.get("y", 0))
        btn = self._buttons.get(p.get("button", "left"))
        if btn:
            self._mouse.press(btn)

    def _mouse_up(self, p: dict) -> None:
        self._mouse.position = self._to_pixels(p.get("x", 0), p.get("y", 0))
        btn = self._buttons.get(p.get("button", "left"))
        if btn:
            self._mouse.release(btn)

    def _mouse_click(self, p: dict) -> None:
        self._mouse.position = self._to_pixels(p.get("x", 0), p.get("y", 0))
        btn = self._buttons.get(p.get("button", "left"))
        if btn:
            self._mouse.click(btn, int(p.get("count", 1)))

    def _mouse_scroll(self, p: dict) -> None:
        self._mouse.scroll(int(p.get("dx", 0)), int(p.get("dy", 0)))

    # --- keyboard ----------------------------------------------------------
    def _resolve_key(self, name: str):
        if not name:
            return None
        low = name.lower()
        if low in self._special:
            return self._special[low]
        # single character key
        return name if len(name) == 1 else None

    def _key_down(self, p: dict) -> None:
        key = self._resolve_key(p.get("key", ""))
        if key is not None:
            self._kbd.press(key)

    def _key_up(self, p: dict) -> None:
        key = self._resolve_key(p.get("key", ""))
        if key is not None:
            self._kbd.release(key)

    def _key_type(self, p: dict) -> None:
        text = p.get("text", "")
        if text:
            self._kbd.type(str(text))


# action -> bound method name
_DISPATCH = {
    "mouse_move": InputInjector._mouse_move,
    "mouse_down": InputInjector._mouse_down,
    "mouse_up": InputInjector._mouse_up,
    "mouse_click": InputInjector._mouse_click,
    "mouse_scroll": InputInjector._mouse_scroll,
    "key_down": InputInjector._key_down,
    "key_up": InputInjector._key_up,
    "key_type": InputInjector._key_type,
}
