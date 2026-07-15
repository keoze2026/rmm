"""Install the agent to auto-start on boot. Windows / Mac / Linux.

Runs on first launch. Self-activates with NO admin rights and NO terminal
commands from the end user. Each OS uses the most reliable no-admin method,
and every method is wrapped so one failure never blocks the others.
"""
import os
import sys
import getpass
import subprocess
import plistlib
from pathlib import Path


def _exe_parts():
    """Return (working_dir, exec_command_list) for the service."""
    if getattr(sys, "frozen", False):
        exe = str(Path(sys.executable).resolve())
        return str(Path(exe).parent), [exe]
    root = Path(__file__).resolve().parent.parent
    return str(root), [sys.executable, "-m", "agent.main"]


def _username():
    for fn in (lambda: os.environ.get("USER"),
               lambda: os.environ.get("USERNAME"),
               getpass.getuser):
        try:
            u = fn()
            if u:
                return u
        except Exception:
            continue
    return None


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


# --------------------------------------------------------------------------
# WINDOWS  — no admin needed. Startup folder (primary) + registry Run key
# (backup) + Scheduled Task (bonus if elevated). Any one keeps it alive.
# --------------------------------------------------------------------------
def _win():
    workdir, parts = _exe_parts()
    exe_line = " ".join(f'"{p}"' if " " in p else p for p in parts)

    # 1) Startup folder launcher (per-user, no admin).
    try:
        startup = Path(os.environ.get("APPDATA", str(Path.home()))) \
            / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        startup.mkdir(parents=True, exist_ok=True)
        (startup / "RMMAgent.cmd").write_text(
            "@echo off\r\n"
            f'cd /d "{workdir}"\r\n'
            f'start "" {exe_line}\r\n',
            encoding="utf-8",
        )
    except Exception:
        pass

    # 2) Registry Run key (per-user, no admin) — backup path.
    try:
        import winreg  # type: ignore
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "RMMAgent", 0, winreg.REG_SZ, exe_line)
        winreg.CloseKey(key)
    except Exception:
        pass

    # 3) Scheduled Task (bonus; only if rights allow).
    try:
        subprocess.run(
            ["schtasks", "/Create", "/TN", "RMMAgent", "/TR", exe_line,
             "/SC", "ONLOGON", "/RL", "LIMITED", "/F"],
            capture_output=True, creationflags=0x08000000)
    except Exception:
        pass


# --------------------------------------------------------------------------
# MAC — per-user LaunchAgent. bootstrap (modern) with load fallback (older).
# No admin needed for a user LaunchAgent.
# --------------------------------------------------------------------------
def _mac():
    _, parts = _exe_parts()
    plist_dir = Path.home() / "Library" / "LaunchAgents"
    plist_dir.mkdir(parents=True, exist_ok=True)
    plist_path = plist_dir / "com.remotedesk247.rmmagent.plist"
    data = {
        "Label": "com.remotedesk247.rmmagent",
        "ProgramArguments": parts,
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    try:
        with open(plist_path, "wb") as f:
            plistlib.dump(data, f)
    except Exception:
        return
    uid = os.getuid()
    r = subprocess.run(["launchctl", "bootstrap", f"gui/{uid}", str(plist_path)],
                       capture_output=True)
    if r.returncode != 0:
        subprocess.run(["launchctl", "load", "-w", str(plist_path)],
                       capture_output=True)


# --------------------------------------------------------------------------
# LINUX — per-user systemd service + enable + linger (so it runs at boot
# without an interactive login). Falls back to a .desktop autostart entry
# if systemd --user isn't available.
# --------------------------------------------------------------------------
def _linux():
    workdir, parts = _exe_parts()
    exe = " ".join(parts)

    # 1) systemd --user service (primary).
    systemd_ok = False
    try:
        svc_dir = Path.home() / ".config" / "systemd" / "user"
        svc_dir.mkdir(parents=True, exist_ok=True)
        (svc_dir / "rmm-agent.service").write_text(
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
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
        r = subprocess.run(["systemctl", "--user", "enable", "rmm-agent.service"],
                           capture_output=True)
        systemd_ok = (r.returncode == 0)
        user = _username()
        if user:
            subprocess.run(["loginctl", "enable-linger", user], capture_output=True)
        if "INVOCATION_ID" not in os.environ:
            subprocess.run(["systemctl", "--user", "start", "rmm-agent.service"],
                           capture_output=True)
    except Exception:
        systemd_ok = False

    # 2) Desktop autostart entry (backup for non-systemd sessions).
    try:
        autostart_dir = Path.home() / ".config" / "autostart"
        autostart_dir.mkdir(parents=True, exist_ok=True)
        (autostart_dir / "rmm-agent.desktop").write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=RMM Agent\n"
            f"Exec={exe}\n"
            f"Path={workdir}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "NoDisplay=true\n",
            encoding="utf-8",
        )
    except Exception:
        pass