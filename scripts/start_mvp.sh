#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$ROOT_DIR/.server.pid"
mkdir -p "$LOG_DIR"

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
  sleep 0.5
fi

cd "$ROOT_DIR"
PYTHON_BIN="$ROOT_DIR/server/.venv/bin/python"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

osascript <<OSA
tell application "Terminal"
  activate
  do script "cd \"$ROOT_DIR\" && ./scripts/run_server.sh"
end tell
OSA

for _ in {1..40}; do
  if "$PYTHON_BIN" - <<'PY' >/dev/null 2>&1
import urllib.request
urllib.request.urlopen("http://127.0.0.1:8765/health", timeout=1).read()
PY
  then
    echo "StillFrame MVP started: http://127.0.0.1:8765"
    exit 0
  fi
  sleep 0.25
done

echo "StillFrame MVP failed to start. See $LOG_DIR/server.log"
exit 1
