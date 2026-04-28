from __future__ import annotations

import shutil
from typing import Any

from app.config import DB_PATH
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


def initialize() -> None:
    database.initialize()


def dependency_status() -> dict[str, Any]:
    mpv_path = shutil.which("mpv")
    ffmpeg_path = shutil.which("ffmpeg")
    full_playback_available = bool(mpv_path and ffmpeg_path)
    install_hint = None
    if not full_playback_available:
        install_hint = (
            "Install mpv and ffmpeg for full codec/audio support. "
            "If Homebrew is available, run scripts/bootstrap_macos.sh."
        )
    return {
        "mpv_available": mpv_path is not None,
        "ffmpeg_available": ffmpeg_path is not None,
        "mpv_path": mpv_path,
        "ffmpeg_path": ffmpeg_path,
        "full_playback_available": full_playback_available,
        "install_hint": install_hint,
    }
