#!/bin/zsh

set -euo pipefail

SERVICE_LABEL="com.projectaiv1.telegram-bot"

launchctl kickstart -k "gui/$(id -u)/$SERVICE_LABEL"

echo "Restarted $SERVICE_LABEL"
