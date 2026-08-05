# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the support-session connector (Windows).

Same runtime as the always-on agent — it differs only in the executable name.
That name is what carries the support-session code: the server serves this
build as ``rmm-connector__<CODE>.exe`` (see app/api/download.py) and the agent
reads the code back out of it on first run.

Build from the rmm-agent/ directory, with config.json present:
    pyinstaller rmm-connector-windows.spec
"""
import os
import sys

from PyInstaller.utils.hooks import collect_all, collect_data_files

datas = []
binaries = []
hiddenimports = []

# server_url + enroll_secret are baked in. Without it the connector has no way
# to reach the server, so fail at build time rather than shipping a dud.
if os.path.exists("config.json"):
    datas.append(("config.json", "."))
else:
    raise SystemExit(
        "[spec] config.json not found — the connector needs server_url and "
        "enroll_secret baked in. Copy config.example.json and fill it in."
    )


def _add(pkg):
    try:
        d, b, h = collect_all(pkg)
        datas.extend(d)
        binaries.extend(b)
        hiddenimports.extend(h)
    except Exception as exc:
        print(f"[spec] skipping {pkg}: {exc}")


for pkg in ("PIL", "mss", "plyer", "websockets", "psutil"):
    _add(pkg)
_add("pynput")
_add("pystray")

if sys.platform.startswith("win"):
    hiddenimports += ["mss.windows", "pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32"]
elif sys.platform == "darwin":
    hiddenimports += ["mss.darwin", "pynput.keyboard._darwin", "pynput.mouse._darwin", "pystray._darwin"]
else:
    hiddenimports += ["mss.linux", "pynput.keyboard._xorg", "pynput.mouse._xorg",
                      "pystray._xorg", "pystray._appindicator", "pystray._gtk"]

hiddenimports += ["PIL.Image", "PIL.ImageDraw", "certifi"]

# Bundle certifi's CA bundle so TLS verification works on Windows.
try:
    datas += collect_data_files("certifi")
except Exception:
    pass

a = Analysis(
    ["run_agent.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="rmm-connector-windows",
    debug=False, strip=False, upx=True,
    console=False,
)
