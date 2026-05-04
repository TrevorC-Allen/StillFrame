#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="$ROOT_DIR/server/.venv/bin/python3"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" -m pytest

unset ELECTRON_RUN_AS_NODE
export ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"

npm --prefix "$ROOT_DIR/app" install
npm --prefix "$ROOT_DIR/app" run build

if command -v swift >/dev/null 2>&1; then
  swift build --package-path "$ROOT_DIR/clients/apple/StillFrameApple"
else
  echo "swift not found; skipping Apple client build" >&2
fi
