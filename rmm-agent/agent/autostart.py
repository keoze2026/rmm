"""Install the agent to auto-start on boot. Windows / Mac / Linux."""
import os
import sys
import subprocess
import plistlib
from pathlib import Path


def _exe_parts():
    """Return (working_dir, exec_command) for the service."""
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return str(Path(exe).parent), exe
    # dev mode: run the module from the project root
    root = Path(__file__).resolve().parent.parent
    return str(root), f"{sys.executable} -m agent.main"


def install_autostart() -> None:
    try:
        if sys.platform.startswith("win"):
            _win()
        elif sys.platform == "darwin":
            _mac()
        elif sys.platform.startswith("linux"):
            _linux()
    except Exception:
        pass


def _win():
    _, exe = _exe_parts()
    subprocess.run([
        "schtasks", "/Create", "/TN", "RMMAgent", "/TR", exe,
        "/SC", "ONLOGON", "/RL", "LIMITED", "/F"
    ], check=False, creationflags=0x08000000)


def _mac():
    _, exe = _exe_parts()
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.remotedesk247.rmmagent.plist"
    if plist_path.exists():
        return
    prog_args = exe.split() if " " in exe else [exe]
    data = {
        "Label": "com.remotedesk247.rmmagent",
        "ProgramArguments": prog_args,
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    with open(plist_path, "wb") as f:
        plistlib.dump(data, f)
    subprocess.run(["launchctl", "load", str(plist_path)], check=False)


def _linux():
    workdir, exe = _exe_parts()
    svc_dir = Path.home() / ".config" / "systemd" / "user"
    svc_dir.mkdir(parents=True, exist_ok=True)
    svc = svc_dir / "rmm-agent.service"
    svc.write_text(
        "[Unit]\n"
        "Description=RMM Agent\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        f"WorkingDirectory={workdir}\n"
        f"ExecStart={exe}\n"
        "Restart=always\n"
        "RestartSec=10\n\n"
        "[Install]\n"
        "WantedBy=default.target\n",
        encoding="utf-8",
    )
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "--user", "enable", "--now", "rmm-agent.service"], check=False)
    try:
        subprocess.run(["loginctl", "enable-linger", os.getlogin()], check=False)
    except Exception:
        pass
