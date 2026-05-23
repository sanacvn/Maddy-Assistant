#!/bin/zsh

set -euo pipefail

SCRIPT_DIR=${0:A:h}
PROJECT_ROOT=${SCRIPT_DIR:h}
SERVICE_LABEL="com.projectaiv1.telegram-bot"
TEMPLATE_PATH="$PROJECT_ROOT/ops/launchd/${SERVICE_LABEL}.plist.template"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/${SERVICE_LABEL}.plist"
STDOUT_LOG="$PROJECT_ROOT/var/log/${SERVICE_LABEL}.out.log"
STDERR_LOG="$PROJECT_ROOT/var/log/${SERVICE_LABEL}.err.log"
RUN_SCRIPT="$PROJECT_ROOT/scripts/run_bot.sh"

mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_ROOT/var/log"

chmod +x "$RUN_SCRIPT"

escaped_project_root=${PROJECT_ROOT//\//\\/}
escaped_run_script=${RUN_SCRIPT//\//\\/}
escaped_stdout_log=${STDOUT_LOG//\//\\/}
escaped_stderr_log=${STDERR_LOG//\//\\/}

sed \
  -e "s/__PROJECT_ROOT__/${escaped_project_root}/g" \
  -e "s/__RUN_SCRIPT__/${escaped_run_script}/g" \
  -e "s/__STDOUT_LOG__/${escaped_stdout_log}/g" \
  -e "s/__STDERR_LOG__/${escaped_stderr_log}/g" \
  "$TEMPLATE_PATH" > "$TARGET_PLIST"

launchctl bootout "gui/$(id -u)/$SERVICE_LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PLIST"
launchctl enable "gui/$(id -u)/$SERVICE_LABEL"
launchctl kickstart -k "gui/$(id -u)/$SERVICE_LABEL"

echo "Installed $SERVICE_LABEL"
echo "plist: $TARGET_PLIST"
echo "stdout: $STDOUT_LOG"
echo "stderr: $STDERR_LOG"
