"""Remote file operations.

Browse, download, and upload files on the endpoint. Runs with the permissions
of the user the agent runs as — it does not escalate. Like the terminal, these
operations are only honored while a remote session is active.

Downloads stream as base64 `file_chunk` messages so large files don't have to
fit in one frame; uploads arrive the same way and are written out.
"""
from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

CHUNK = 256 * 1024  # 256 KB per file_chunk


def _home() -> str:
    return os.path.expanduser("~")


def list_dir(path: str | None) -> dict:
    """Return directory entries. Defaults to the user's home."""
    target = Path(path or _home()).expanduser()
    try:
        target = target.resolve()
    except OSError:
        pass

    if not target.exists():
        return {"ok": False, "path": str(target), "error": "not found"}
    if not target.is_dir():
        return {"ok": False, "path": str(target), "error": "not a directory"}

    entries = []
    try:
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            try:
                st = child.stat()
                entries.append(
                    {
                        "name": child.name,
                        "is_dir": stat.S_ISDIR(st.st_mode),
                        "size": st.st_size,
                        "mtime": int(st.st_mtime),
                    }
                )
            except OSError:
                # Unreadable entry — list the name, mark unknown.
                entries.append({"name": child.name, "is_dir": False, "size": 0, "mtime": 0})
    except PermissionError:
        return {"ok": False, "path": str(target), "error": "permission denied"}

    parent = str(target.parent) if target.parent != target else None
    return {"ok": True, "path": str(target), "parent": parent, "entries": entries}


def iter_file_chunks(path: str):
    """Yield (seq, total_chunks, base64_data) for a file, or raise OSError."""
    p = Path(path).expanduser()
    size = p.stat().st_size
    total = max(1, (size + CHUNK - 1) // CHUNK)
    with p.open("rb") as fh:
        seq = 0
        while True:
            block = fh.read(CHUNK)
            if not block:
                if seq == 0:
                    # empty file: emit one empty chunk so the admin gets a result
                    yield (0, 1, "")
                break
            yield (seq, total, base64.b64encode(block).decode("ascii"))
            seq += 1


def write_chunk(path: str, data_b64: str, *, first: bool) -> None:
    """Append a base64 chunk to a file (truncate on the first chunk)."""
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if first else "ab"
    with p.open(mode) as fh:
        fh.write(base64.b64decode(data_b64))