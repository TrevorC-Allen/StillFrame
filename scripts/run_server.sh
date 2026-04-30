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
exec "$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8765
