#!/bin/bash
# install_agent.sh — install the RMM agent as a per-user LaunchAgent on macOS.
#
# Multi-user design: a LaunchAgent in /Library/LaunchAgents loads in EVERY
# user's GUI session at login, so the tray icon + session notification are
# visible to whoever is using the Mac. (A LaunchDaemon would run as root with
# no GUI — wrong for a consent-aware agent.)
#
# Run with sudo:
#   sudo ./install_agent.sh "wss://156.67.25.167:8765" "<machine-token>"
#
# Assumes "Remote Support Agent.app" (your PyInstaller build) is already in
# /Applications.

set -euo pipefail

SERVER_URL="${1:?usage: install_agent.sh <server_url> <token>}"
TOKEN="${2:?usage: install_agent.sh <server_url> <token>}"

PLIST_SRC="$(dirname "$0")/net.keozx.rmmagent.plist"
PLIST_DST="/Library/LaunchAgents/net.keozx.rmmagent.plist"
DATA_DIR="/Library/Application Support/RMAgent"

echo "Installing RMM agent LaunchAgent..."

# 1) Shared, machine-wide config (one token for all users on this Mac).
mkdir -p "$DATA_DIR"
cat > "$DATA_DIR/config.json" <<EOF
{
  "server_url": "$SERVER_URL",
  "token": "$TOKEN",
  "show_tray_icon": true,
  "notify_on_session": true,
  "allow_remote_input": true
}
EOF
chmod 644 "$DATA_DIR/config.json"   # readable by all users

# 2) Install the LaunchAgent (root-owned, world-readable).
cp "$PLIST_SRC" "$PLIST_DST"
chown root:wheel "$PLIST_DST"
chmod 644 "$PLIST_DST"

# 3) Load it into the currently logged-in user's GUI session now.
CONSOLE_USER="$(stat -f%Su /dev/console)"
CONSOLE_UID="$(id -u "$CONSOLE_USER")"
if [ "$CONSOLE_USER" != "root" ]; then
    launchctl bootstrap "gui/$CONSOLE_UID" "$PLIST_DST" 2>/dev/null || \
        launchctl load -w "$PLIST_DST" 2>/dev/null || true
    echo "Loaded for current user: $CONSOLE_USER"
fi

cat <<'NOTE'

Done. IMPORTANT — grant permissions once per user (macOS enforces this):
  System Settings -> Privacy & Security ->
    * Screen Recording   -> enable "Remote Support Agent"
    * Accessibility       -> enable "Remote Support Agent"
Until granted, screen capture and input control silently do nothing.
NOTE