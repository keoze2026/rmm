"""Agent entrypoint.

Run with:  python -m agent.main   (or the PyInstaller-built executable)

Wires the visible presence (tray icon), loads config, and runs the connection
loop until interrupted. The tray icon is started before the network loop so the
machine's user can always see the agent is present.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from agent.config import AgentConfig, resolve_config_path
from agent.connection import AgentConnection
from agent.presence import build_presence
from agent.singleton import SingleInstance


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )


async def _amain(config: AgentConfig, *, headless: bool) -> int:
    presence = build_presence(enabled=config.show_tray_icon and not headless)
    conn = AgentConnection(config, presence)

    loop = asyncio.get_running_loop()
    stop = asyncio.Event()

    def _request_stop() -> None:
        stop.set()
        conn.stop()

    # Graceful shutdown on SIGINT/SIGTERM where supported (POSIX).
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, AttributeError):  # Windows
            pass

    runner = asyncio.create_task(conn.run_forever())
    try:
        await runner
    except asyncio.CancelledError:
        pass
    finally:
        presence.stop()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="RMM consent-aware endpoint agent")
    parser.add_argument("--config", default=None,
                        help="path to config.json (default: auto-detect)")
    parser.add_argument("--server", help="override server_url (e.g. wss://host:8765)")
    parser.add_argument("--token", help="override per-machine token")
    parser.add_argument("--headless", action="store_true",
                        help="run without a tray icon (dev/build servers only)")
    parser.add_argument("--allow-multiple", action="store_true",
                        help="skip the single-instance lock (testing only)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    # One agent per machine, even across multiple logged-in users.
    instance = None
    if not args.allow_multiple:
        instance = SingleInstance()
        if not instance.acquire():
            print("[agent] another agent instance is already running on this machine.",
                  file=sys.stderr)
            return 0

    from pathlib import Path
    config_path = Path(args.config) if args.config else resolve_config_path()
    config = AgentConfig.load(config_path)
    if args.server:
        config.server_url = args.server
    if args.token:
        config.token = args.token

    if not config.token:
        print("[agent] no token configured. Set it in config.json or pass --token.",
              file=sys.stderr)
        return 2

    try:
        return asyncio.run(_amain(config, headless=args.headless))
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())