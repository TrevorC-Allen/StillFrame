#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT_DIR/app"
APP_NAME="StillFrame.app"
BUILT_APP="$APP_DIR/release-local/mac-arm64/$APP_NAME"
CLEAN_DIR="$APP_DIR/release-local/mac-arm64-clean"
CLEAN_APP="$CLEAN_DIR/$APP_NAME"
INSTALLED_APP="/Applications/$APP_NAME"
ELECTRON_MIRROR="${ELECTRON_MIRROR:-https://npmmirror.com/mirrors/electron/}"

unset ELECTRON_RUN_AS_NODE
export ELECTRON_MIRROR

cd "$ROOT_DIR"

npm --prefix "$APP_DIR" install
npm --prefix "$APP_DIR" run build

CSC_IDENTITY_AUTO_DISCOVERY=false \
ELECTRON_MIRROR="$ELECTRON_MIRROR" \
"$APP_DIR/node_modules/.bin/electron-builder" \
  --projectDir "$APP_DIR" \
  --mac \
  --dir \
  --config.directories.output=release-local

rm -rf "$CLEAN_DIR"
mkdir -p "$CLEAN_DIR"
ditto --noextattr --norsrc "$BUILT_APP" "$CLEAN_APP"

"$CLEAN_APP/Contents/Resources/StillFrame/server/.venv/bin/python" - <<'PY'
import fastapi, pydantic, uvicorn
print(f"packaged-backend-ok fastapi={fastapi.__version__} uvicorn={uvicorn.__version__} pydantic={pydantic.__version__}")
PY

identity="$(
  security find-identity -v -p codesigning |
    awk -F'"' '/Developer ID Application|Apple Development/ { print $2; exit }'
)"
if [[ -z "$identity" ]]; then
  identity="-"
fi

codesign --force --deep --sign "$identity" "$CLEAN_APP"
codesign --verify --deep --verbose=2 "$CLEAN_APP"
spctl --assess --type execute --verbose "$CLEAN_APP" || true

port_pids="$(lsof -ti tcp:8765 || true)"
if [[ -n "$port_pids" ]]; then
  kill $port_pids || true
fi

pkill -f "$INSTALLED_APP/Contents/MacOS/StillFrame" 2>/dev/null || true
rm -rf "$INSTALLED_APP"
ditto "$CLEAN_APP" "$INSTALLED_APP"

codesign --verify --deep --verbose=2 "$INSTALLED_APP"
spctl --assess --type execute --verbose "$INSTALLED_APP" || true

open -a "$INSTALLED_APP"

for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:8765/health" > /tmp/stillframe_install_health.json 2>/dev/null; then
    cat /tmp/stillframe_install_health.json
    echo
    exit 0
  fi
  sleep 0.5
done

echo "StillFrame installed, but backend health check timed out." >&2
exit 1
