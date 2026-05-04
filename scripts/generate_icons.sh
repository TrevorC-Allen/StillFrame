#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE="$ROOT_DIR/app/assets/icons/stillframe-icon.svg"
STRIP_ALPHA="$ROOT_DIR/scripts/strip_png_alpha.py"
ELECTRON_ICON_DIR="$ROOT_DIR/app/assets/icons"
APPLE_ICONSET="$ROOT_DIR/clients/apple/StillFrameApple/Resources/Assets.xcassets/AppIcon.appiconset"
TMP_DIR="$(mktemp -d)"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if ! command -v qlmanage >/dev/null 2>&1; then
  echo "qlmanage is required to render the SVG icon on macOS."
  exit 1
fi

if ! command -v sips >/dev/null 2>&1; then
  echo "sips is required to resize icon assets on macOS."
  exit 1
fi

if ! command -v iconutil >/dev/null 2>&1; then
  echo "iconutil is required to generate the macOS icns file."
  exit 1
fi

mkdir -p "$ELECTRON_ICON_DIR" "$APPLE_ICONSET"

qlmanage -t -s 1024 -o "$TMP_DIR" "$SOURCE" >/dev/null 2>&1
BASE_PNG="$TMP_DIR/$(basename "$SOURCE").png"
if [ ! -f "$BASE_PNG" ]; then
  echo "Could not render $SOURCE"
  exit 1
fi

cp "$SOURCE" "$ROOT_DIR/app/public/favicon.svg"
cp "$SOURCE" "$ROOT_DIR/app/public/stillframe-mark.svg"
cp "$SOURCE" "$ROOT_DIR/app/public/stillframe-icon.svg"
sips -s format png "$BASE_PNG" --out "$TMP_DIR/stillframe-icon-1024-rgba.png" >/dev/null
python3 "$STRIP_ALPHA" "$TMP_DIR/stillframe-icon-1024-rgba.png" "$ELECTRON_ICON_DIR/stillframe-icon-1024.png"

ICONSET="$TMP_DIR/stillframe.iconset"
mkdir -p "$ICONSET"

mac_icon() {
  local point_size="$1"
  local scale="$2"
  local pixels=$((point_size * scale))
  local suffix=""
  if [ "$scale" -eq 2 ]; then
    suffix="@2x"
  fi
  local rgba="$TMP_DIR/icon_${point_size}x${point_size}${suffix}-rgba.png"
  local rgb="$ICONSET/icon_${point_size}x${point_size}${suffix}.png"
  sips -z "$pixels" "$pixels" "$BASE_PNG" --out "$rgba" >/dev/null
  python3 "$STRIP_ALPHA" "$rgba" "$rgb"
}

mac_icon 16 1
mac_icon 16 2
mac_icon 32 1
mac_icon 32 2
mac_icon 128 1
mac_icon 128 2
mac_icon 256 1
mac_icon 256 2
mac_icon 512 1
mac_icon 512 2
iconutil -c icns "$ICONSET" -o "$ELECTRON_ICON_DIR/stillframe.icns"

apple_png() {
  local filename="$1"
  local pixels="$2"
  local rgba="$TMP_DIR/$filename"
  sips -z "$pixels" "$pixels" "$BASE_PNG" --out "$rgba" >/dev/null
  python3 "$STRIP_ALPHA" "$rgba" "$APPLE_ICONSET/$filename"
}

apple_png "Icon-20.png" 20
apple_png "Icon-20@2x.png" 40
apple_png "Icon-20@3x.png" 60
apple_png "Icon-29.png" 29
apple_png "Icon-29@2x.png" 58
apple_png "Icon-29@3x.png" 87
apple_png "Icon-40.png" 40
apple_png "Icon-40@2x.png" 80
apple_png "Icon-40@3x.png" 120
apple_png "Icon-60@2x.png" 120
apple_png "Icon-60@3x.png" 180
apple_png "Icon-76.png" 76
apple_png "Icon-76@2x.png" 152
apple_png "Icon-83.5@2x.png" 167
apple_png "Icon-1024.png" 1024
apple_png "Icon-mac-16.png" 16
apple_png "Icon-mac-16@2x.png" 32
apple_png "Icon-mac-32.png" 32
apple_png "Icon-mac-32@2x.png" 64
apple_png "Icon-mac-128.png" 128
apple_png "Icon-mac-128@2x.png" 256
apple_png "Icon-mac-256.png" 256
apple_png "Icon-mac-256@2x.png" 512
apple_png "Icon-mac-512.png" 512
apple_png "Icon-mac-512@2x.png" 1024

cat > "$APPLE_ICONSET/Contents.json" <<'JSON'
{
  "images": [
    { "idiom": "iphone", "size": "20x20", "scale": "2x", "filename": "Icon-20@2x.png" },
    { "idiom": "iphone", "size": "20x20", "scale": "3x", "filename": "Icon-20@3x.png" },
    { "idiom": "iphone", "size": "29x29", "scale": "2x", "filename": "Icon-29@2x.png" },
    { "idiom": "iphone", "size": "29x29", "scale": "3x", "filename": "Icon-29@3x.png" },
    { "idiom": "iphone", "size": "40x40", "scale": "2x", "filename": "Icon-40@2x.png" },
    { "idiom": "iphone", "size": "40x40", "scale": "3x", "filename": "Icon-40@3x.png" },
    { "idiom": "iphone", "size": "60x60", "scale": "2x", "filename": "Icon-60@2x.png" },
    { "idiom": "iphone", "size": "60x60", "scale": "3x", "filename": "Icon-60@3x.png" },
    { "idiom": "ipad", "size": "20x20", "scale": "1x", "filename": "Icon-20.png" },
    { "idiom": "ipad", "size": "20x20", "scale": "2x", "filename": "Icon-20@2x.png" },
    { "idiom": "ipad", "size": "29x29", "scale": "1x", "filename": "Icon-29.png" },
    { "idiom": "ipad", "size": "29x29", "scale": "2x", "filename": "Icon-29@2x.png" },
    { "idiom": "ipad", "size": "40x40", "scale": "1x", "filename": "Icon-40.png" },
    { "idiom": "ipad", "size": "40x40", "scale": "2x", "filename": "Icon-40@2x.png" },
    { "idiom": "ipad", "size": "76x76", "scale": "1x", "filename": "Icon-76.png" },
    { "idiom": "ipad", "size": "76x76", "scale": "2x", "filename": "Icon-76@2x.png" },
    { "idiom": "ipad", "size": "83.5x83.5", "scale": "2x", "filename": "Icon-83.5@2x.png" },
    { "idiom": "ios-marketing", "size": "1024x1024", "scale": "1x", "filename": "Icon-1024.png" },
    { "idiom": "mac", "size": "16x16", "scale": "1x", "filename": "Icon-mac-16.png" },
    { "idiom": "mac", "size": "16x16", "scale": "2x", "filename": "Icon-mac-16@2x.png" },
    { "idiom": "mac", "size": "32x32", "scale": "1x", "filename": "Icon-mac-32.png" },
    { "idiom": "mac", "size": "32x32", "scale": "2x", "filename": "Icon-mac-32@2x.png" },
    { "idiom": "mac", "size": "128x128", "scale": "1x", "filename": "Icon-mac-128.png" },
    { "idiom": "mac", "size": "128x128", "scale": "2x", "filename": "Icon-mac-128@2x.png" },
    { "idiom": "mac", "size": "256x256", "scale": "1x", "filename": "Icon-mac-256.png" },
    { "idiom": "mac", "size": "256x256", "scale": "2x", "filename": "Icon-mac-256@2x.png" },
    { "idiom": "mac", "size": "512x512", "scale": "1x", "filename": "Icon-mac-512.png" },
    { "idiom": "mac", "size": "512x512", "scale": "2x", "filename": "Icon-mac-512@2x.png" }
  ],
  "info": {
    "author": "xcode",
    "version": 1
  }
}
JSON

echo "Generated StillFrame icons."
