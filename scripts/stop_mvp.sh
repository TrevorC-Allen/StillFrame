#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.server.pid"
LABEL="com.stillframe.mvp"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
rm -f "$PLIST"

if [ -f "$PID_FILE" ]; then
  PID="$(cat "$PID_FILE")"
  if kill -0 "$PID" >/dev/null 2>&1; then
    kill "$PID"
  fi
  rm -f "$PID_FILE"
fi

PIDS="$(lsof -ti tcp:8765 || true)"
if [ -n "$PIDS" ]; then
  kill $PIDS || true
fi

echo "StillFrame MVP stopped."
