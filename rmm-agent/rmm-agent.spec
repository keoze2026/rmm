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
    excludes=["tkinter", "matplotlib", "numpy"],
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
