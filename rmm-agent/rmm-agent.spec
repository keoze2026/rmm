# -*- mode: python ; coding: utf-8 -*-
import sys
from PyInstaller.utils.hooks import collect_all

datas = [('config.json', '.')]
binaries = []
hiddenimports = []


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

# Linux tray icon: without PyGObject bundled, pystray falls back to its X11
# backend, which paints a flat rectangle instead of the icon. Icon-only.
if sys.platform.startswith("linux"):
    _add("gi")

if sys.platform.startswith("win"):
    # Composition-aware capture for the privacy blank (see capture_win.py).
    _add("windows_capture")
    _add("numpy")
    hiddenimports += ["mss.windows", "pynput.keyboard._win32", "pynput.mouse._win32", "pystray._win32",
                      "windows_capture", "numpy"]
elif sys.platform == "darwin":
    hiddenimports += ["mss.darwin", "pynput.keyboard._darwin", "pynput.mouse._darwin", "pystray._darwin"]
else:
    hiddenimports += ["mss.linux", "pynput.keyboard._xorg", "pynput.mouse._xorg",
                      "pystray._xorg", "pystray._appindicator", "pystray._gtk"]

hiddenimports += ["PIL.Image", "PIL.ImageDraw", "certifi"]

# Bundle certifi's CA bundle so TLS verification works on Windows.
try:
    from PyInstaller.utils.hooks import collect_data_files
    datas += collect_data_files("certifi")
except Exception:
    pass

a = Analysis(
    ["run_agent.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # tkinter kept: privacy-blank window (feature 6)
    # numpy no longer excluded: Windows.Graphics.Capture needs it (Windows only;
    # it isn't installed on Linux/macOS, so nothing to bundle there anyway).
    excludes=["matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name="rmm-agent",
    debug=False, strip=False, upx=True,
    console=False,
)

if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name="Remote Support Agent.app",
        icon=None,
        bundle_identifier="com.remotedesk247.rmmagent",
        info_plist={"NSHighResolutionCapable": True, "LSUIElement": True},
    )
