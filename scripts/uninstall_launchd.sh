#!/bin/zsh

set -euo pipefail

SERVICE_LABEL="com.projectaiv1.telegram-bot"
TARGET_PLIST="$HOME/Library/LaunchAgents/${SERVICE_LABEL}.plist"

launchctl bootout "gui/$(id -u)/$SERVICE_LABEL" >/dev/null 2>&1 || true
rm -f "$TARGET_PLIST"

echo "Removed $SERVICE_LABEL"
