from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from typing import Any

from app.config import DB_PATH, VIDEO_EXTENSIONS
from app.database import Database
from app.services.library_service import LibraryService
from app.services.media_service import MediaService
from player.mpv_controller import MPVController
from player.subtitle_manager import SubtitleManager


database = Database(DB_PATH)
library_service = LibraryService(database)
media_service = MediaService(library_service)
subtitle_manager = SubtitleManager()
mpv_controller = MPVController()

VERSION_TIMEOUT_SECONDS = 1.0
DIAGNOSTICS_URL = "/diagnostics/playback"


def initialize() -> None:
    database.initialize()


def dependency_status() -> dict[str, Any]:
    diagnostics = playback_diagnostics()
    mpv = diagnostics["mpv"]
    ffmpeg = diagnostics["ffmpeg"]
    return {
        "mpv_available": mpv["present"],
        "ffmpeg_available": ffmpeg["present"],
        "mpv_path": mpv["path"],
        "ffmpeg_path": ffmpeg["path"],
        "full_playback_available": diagnostics["full_playback_available"],
        "install_hint": diagnostics["install_hint"],
        "diagnostics_url": DIAGNOSTICS_URL,
    }


def playback_diagnostics() -> dict[str, Any]:
    mpv = _tool_diagnostic("mpv", ["--version"])
    ffmpeg = _tool_diagnostic("ffmpeg", ["-version"])
    browser_preview_supported = bool(VIDEO_EXTENSIONS)
    full_playback_available = bool(mpv["present"] and ffmpeg["present"])
    issues: list[dict[str, str]] = []

    if not browser_preview_supported:
        issues.append(
            {
                "code": "browser_stream_unavailable",
                "severity": "error",
                "message": "The local API cannot expose media byte streams for browser preview.",
                "action": "Restart StillFrame after checking the backend media route configuration.",
            }
        )
    if not mpv["present"]:
        issues.append(
            {
                "code": "mpv_missing",
                "severity": "error",
                "message": "mpv is not installed or is not on PATH, so native playback and fullscreen are unavailable.",
                "action": "Install mpv, then restart StillFrame so the backend can find it.",
            }
        )
    if not ffmpeg["present"]:
        issues.append(
            {
                "code": "ffmpeg_missing",
                "severity": "error",
                "message": "ffmpeg is not installed or is not on PATH, so codec and audio support may be incomplete.",
                "action": "Install ffmpeg, then restart StillFrame so the backend can find it.",
            }
        )

    install_hint = None
    if issues:
        install_hint = (
            "Install mpv and ffmpeg for full codec/audio support. "
            "If Homebrew is available, run scripts/bootstrap_macos.sh."
        )

    return {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "mpv": mpv,
        "ffmpeg": ffmpeg,
        "browser_preview_supported": browser_preview_supported,
        "full_playback_available": full_playback_available,
        "issues": issues,
        "install_hint": install_hint,
    }


def _tool_diagnostic(name: str, version_args: list[str]) -> dict[str, Any]:
    path = shutil.which(name)
    if not path:
        return {"present": False, "path": None, "version": None}
    return {
        "present": True,
        "path": path,
        "version": _read_version_line([path, *version_args]),
    }


def _read_version_line(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError):
        return None

    output = result.stdout or result.stderr or ""
    for line in output.splitlines():
        version = line.strip()
        if version:
            return version
    return None
