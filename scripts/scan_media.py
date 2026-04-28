from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SERVER_DIR = ROOT_DIR / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

from app.config import VIDEO_EXTENSIONS


def main() -> None:
    parser = argparse.ArgumentParser(description="Print playable media files under a folder.")
    parser.add_argument("path")
    args = parser.parse_args()

    root = Path(args.path).expanduser().resolve()
    for media in sorted(root.rglob("*")):
        if media.is_file() and media.suffix.lower() in VIDEO_EXTENSIONS:
            print(media)


if __name__ == "__main__":
    main()
