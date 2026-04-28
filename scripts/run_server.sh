#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/server"

if [ -d ".venv" ]; then
  . .venv/bin/activate
fi

export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/server:${PYTHONPATH:-}"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8765

