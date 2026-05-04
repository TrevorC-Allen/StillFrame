#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/server"

if [ -x ".venv/bin/python3" ]; then
  PYTHON_BIN=".venv/bin/python3"
else
  PYTHON_BIN="python3"
fi

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/server:${PYTHONPATH:-}"
export STILLFRAME_HOST="${STILLFRAME_HOST:-0.0.0.0}"
export STILLFRAME_PORT="${STILLFRAME_PORT:-8765}"

echo "StillFrame API is exposed on this Mac at http://<mac-lan-ip>:$STILLFRAME_PORT"
echo "Use only on a trusted local network."
exec "$PYTHON_BIN" -m uvicorn app.main:app --host "$STILLFRAME_HOST" --port "$STILLFRAME_PORT"
