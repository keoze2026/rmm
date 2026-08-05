"""Per-session connector downloads.

The support-session code reaches the guest's machine through the connector's
*filename*: this route serves the platform build under the name
``rmm-connector__<CODE>.<ext>`` so the agent can read the code back out on
first run (see ``agent/config.py:_code_from_exe_name``) and enroll straight
into that session.

The files on disk keep their plain platform names; only the name the browser
saves changes, via Content-Disposition.

Lives under ``/api`` on purpose: the reverse proxy already forwards ``/api/*``
to this app (the join page's ``/api/support/resolve`` call proves it), so no
proxy change is needed to ship this.
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.database import get_db
from app.models.support_session import SupportSession

log = logging.getLogger("app.api.download")

router = APIRouter(prefix="/api/download", tags=["download"])

# Matches the codes app/api/support.py:_gen_code produces (6 chars today);
# the range leaves room without letting anything odd into a header.
_CODE_RE = re.compile(r"^[A-Z0-9]{4,12}$")

# platform key -> (file on disk, extension for the downloaded name)
_ASSETS: dict[str, tuple[str, str]] = {
    "windows": ("rmm-connector-windows.exe", ".exe"),
    "linux": ("rmm-connector-linux", ""),
    "mac": ("rmm-connector-mac.zip", ".zip"),
}


def _rename_zip_entry(name: str, code: str) -> str:
    """Stamp the code onto the .app bundle and the loose connector binary.

    Only the *names* change; every byte inside Contents/ is copied untouched,
    so the bundle's ad-hoc signature stays valid (it seals paths relative to
    the bundle, not the bundle's own name).
    """
    head, sep, rest = name.partition("/")
    if head.lower().endswith(".app"):
        stem = head[: -len(".app")]
        if not stem.endswith(f"__{code}"):
            head = f"{stem}__{code}.app"
        return head + sep + rest
    return name


def _rewrite_mac_zip(src: Path, code: str) -> bytes:
    """Return the mac zip with the session code stamped into its entry names."""
    out = io.BytesIO()
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        renamed = 0
        for item in zin.infolist():
            data = zin.read(item.filename)
            name = _rename_zip_entry(item.filename, code)
            # A loose top-level executable (the non-bundle fallback binary)
            # carries the code in its own name, like the Windows/Linux builds.
            if "/" not in item.filename and item.external_attr >> 16 & 0o111:
                name = f"rmm-connector__{code}"
            if name != item.filename:
                renamed += 1
            info = zipfile.ZipInfo(name, date_time=item.date_time)
            # Carry the mode bits over — without them the binary loses +x and
            # macOS refuses to launch it.
            info.external_attr = item.external_attr
            info.internal_attr = item.internal_attr
            info.create_system = item.create_system
            info.compress_type = item.compress_type
            zout.writestr(info, data)

    if not renamed:
        # Nothing carried the code, so the connector would enroll unbound —
        # the exact silent failure this route exists to prevent.
        raise RuntimeError(
            f"{src.name} has no .app bundle or executable to stamp with the code"
        )
    return out.getvalue()


@router.get("/connector")
async def download_connector(
    code: str = Query(..., description="support session code"),
    os: str = Query("windows", description="windows | mac | linux"),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    asset = _ASSETS.get(os.strip().lower())
    if asset is None:
        raise HTTPException(404, "unknown platform")

    session_code = code.strip().upper()
    if not _CODE_RE.match(session_code):
        raise HTTPException(400, "invalid code")

    sess = await db.scalar(
        select(SupportSession).where(SupportSession.code == session_code)
    )
    if sess is None or sess.status == "ended":
        raise HTTPException(404, "session not found or ended")

    filename, ext = asset
    path = Path(settings.DOWNLOAD_DIR) / filename
    if not path.is_file():
        raise HTTPException(404, "connector build not available for this platform")

    download_name = f"rmm-connector__{session_code}{ext}"

    # macOS runs from a .app bundle, so the downloaded file's own name never
    # reaches the agent — the code has to be stamped inside the archive.
    if ext == ".zip":
        try:
            payload = await run_in_threadpool(_rewrite_mac_zip, path, session_code)
        except Exception as exc:
            log.exception("failed to stamp %s with code %s", path.name, session_code)
            raise HTTPException(500, "could not prepare the connector") from exc
        return Response(
            content=payload,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )

    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=download_name,
    )
