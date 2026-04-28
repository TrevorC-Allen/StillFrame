#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "StillFrame bootstrap"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

if command -v brew >/dev/null 2>&1; then
  echo "Installing native dependencies with Homebrew..."
  brew install node mpv ffmpeg
else
  echo "Homebrew is not installed. Install Node.js, mpv, and ffmpeg manually, then rerun npm install."
fi

echo "Preparing Python backend..."
cd "$ROOT_DIR/server"
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if command -v npm >/dev/null 2>&1; then
  echo "Installing Electron frontend dependencies..."
  cd "$ROOT_DIR/app"
  npm install
else
  echo "npm is not available yet; skipping frontend install."
fi

echo "Done."

