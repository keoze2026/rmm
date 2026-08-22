"""Wire protocol helpers.

Every WS message is JSON of the shape {"type": "...", ...}. These builders
mirror exactly what the Phase 1 server (app/ws/handlers.py) sends and expects,
so the agent and server stay in lockstep.

Server -> agent:
    {"type": "welcome", "machine_id": "..."}
    {"type": "command", "action": "...", "payload": {...}, "admin_id": "..."}

Agent -> server:
    {"type": "hello", "inventory": {...}}
    {"type": "heartbeat"}
    {"type": "frame", "fmt": "jpeg", "data": "<b64>", "w": W, "h": H, ...}
    {"type": "agent_event", "event": "...", ...}
"""
from __future__ import annotations

import datetime as _dt
from typing import Any

# --- message type constants ------------------------------------------------
# inbound (from server)
WELCOME = "welcome"
COMMAND = "command"

# outbound (to server)
HELLO = "hello"
HEARTBEAT = "heartbeat"
FRAME = "frame"
AGENT_EVENT = "agent_event"

# --- command actions the server/admin can ask the agent to perform ---------
ACTION_SESSION_START = "session_start"
ACTION_SESSION_STOP = "session_stop"
ACTION_MOUSE_MOVE = "mouse_move"
ACTION_MOUSE_DOWN = "mouse_down"
ACTION_MOUSE_UP = "mouse_up"
ACTION_MOUSE_CLICK = "mouse_click"
ACTION_MOUSE_SCROLL = "mouse_scroll"
ACTION_KEY_DOWN = "key_down"
ACTION_KEY_UP = "key_up"
ACTION_KEY_TYPE = "key_type"
ACTION_PING = "ping"

# Terminal actions
ACTION_TERM_START = "term_start"
ACTION_TERM_INPUT = "term_input"
ACTION_TERM_RESIZE = "term_resize"
ACTION_TERM_STOP = "term_stop"

# File actions
ACTION_FS_LIST = "fs_list"
ACTION_FS_READ = "fs_read"
ACTION_FS_WRITE = "fs_write"

# Monitor selection. Additive: every action above is unchanged, and these ride
# the same command envelope, so the server relays them without any change.
ACTION_MONITORS_LIST = "monitors_list"
ACTION_MONITOR_SELECT = "monitor_select"

# Privacy blank (feature 6). Additive; replies ride agent_event, no server change.
ACTION_BLANK_ON = "blank_on"
ACTION_BLANK_OFF = "blank_off"


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def hello(inventory: dict[str, Any]) -> dict:
    return {"type": HELLO, "inventory": inventory}


def heartbeat() -> dict:
    return {"type": HEARTBEAT, "ts": _now_iso()}


def frame(data_b64: str, width: int, height: int, *, monitor: int, seq: int,
          fmt: str = "jpeg") -> dict:
    return {
        "type": FRAME,
        "fmt": fmt,
        "data": data_b64,
        "w": width,
        "h": height,
        "monitor": monitor,
        "seq": seq,
        "ts": _now_iso(),
    }


def agent_event(event: str, **fields: Any) -> dict:
    return {"type": AGENT_EVENT, "event": event, "ts": _now_iso(), **fields}


def terminal_output(term_id: str, data_b64: str) -> dict:
    return {"type": "terminal_output", "term_id": term_id, "data": data_b64}


def file_chunk(transfer_id: str, seq: int, total: int, data_b64: str, *, eof: bool = False) -> dict:
    return {
        "type": "file_chunk",
        "transfer_id": transfer_id,
        "seq": seq,
        "total": total,
        "data": data_b64,
        "eof": eof,
    }

def frame_tiles(tiles: list, width: int, height: int, *, monitor: int = 1,
                seq: int = 0, keyframe: bool = False) -> dict:
    """A frame sent as changed tiles only.

    Deliberately reuses type "frame" so the server relays it unchanged — it
    forwards a fixed set of message types, and a new one would be dropped.
    Consumers tell the two apart by the presence of "tiles".
    """
    return {
        "type": FRAME,
        "tiles": tiles,
        "width": width,
        "height": height,
        "monitor": monitor,
        "seq": seq,
        "keyframe": keyframe,
    }
