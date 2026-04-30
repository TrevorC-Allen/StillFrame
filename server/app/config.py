from __future__ import annotations

import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_DIR = ROOT_DIR / "server"
MEDIA_CACHE_DIR = ROOT_DIR / "media_cache"

DB_PATH = Path(os.environ.get("STILLFRAME_DB_PATH", SERVER_DIR / "stillframe.db"))
HOST = os.environ.get("STILLFRAME_HOST", "127.0.0.1")
PORT = int(os.environ.get("STILLFRAME_PORT", "8765"))
TMDB_API_KEY = os.environ.get("STILLFRAME_TMDB_API_KEY")
TMDB_BEARER_TOKEN = os.environ.get("STILLFRAME_TMDB_BEARER_TOKEN")
TMDB_LANGUAGE = os.environ.get("STILLFRAME_TMDB_LANGUAGE", "zh-CN")

VIDEO_EXTENSIONS = {
    ".3gp",
    ".avi",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogm",
    ".ogv",
    ".rmvb",
    ".ts",
    ".webm",
    ".wmv",
}

SUBTITLE_EXTENSIONS = {".ass", ".srt", ".ssa", ".sub", ".vtt"}
ARTWORK_EXTENSIONS = {".jpg", ".jpeg", ".png", ".svg", ".webp"}
