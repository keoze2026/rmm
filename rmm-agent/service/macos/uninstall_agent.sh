#!/bin/bash
# uninstall_agent.sh — remove the RMM agent LaunchAgent on macOS. Run with sudo.
set -uo pipefail

PLIST_DST="/Library/LaunchAgents/net.keozx.rmmagent.plist"
DATA_DIR="/Library/Application Support/RMAgent"

CONSOLE_USER="$(stat -f%Su /dev/console)"
CONSOLE_UID="$(id -u "$CONSOLE_USER" 2>/dev/null || echo 0)"

echo "Unloading LaunchAgent..."
launchctl bootout "gui/$CONSOLE_UID" "$PLIST_DST" 2>/dev/null || \
    launchctl unload -w "$PLIST_DST" 2>/dev/null || true

rm -f "$PLIST_DST"
rm -rf "$DATA_DIR"

echo "Done. (You may also remove /Applications/Remote Support Agent.app)"