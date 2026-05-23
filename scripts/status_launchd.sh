#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}
SERVICE_LABEL="com.projectaiv1.telegram-bot"
STDOUT_LOG="$PROJECT_ROOT/var/log/${SERVICE_LABEL}.out.log"
STDERR_LOG="$PROJECT_ROOT/var/log/${SERVICE_LABEL}.err.log"

echo "Service label: $SERVICE_LABEL"
echo
launchctl print "gui/$(id -u)/$SERVICE_LABEL" || true
echo
echo "stdout log: $STDOUT_LOG"
test -f "$STDOUT_LOG" && tail -n 20 "$STDOUT_LOG" || echo "stdout log not created yet"
echo
echo "stderr log: $STDERR_LOG"
test -f "$STDERR_LOG" && tail -n 20 "$STDERR_LOG" || echo "stderr log not created yet"
