from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from app.config import MEDIA_CACHE_DIR
from app.models.schemas import CacheDiagnosticsResponse, PlaybackDiagnosticsResponse
from app.state import playback_diagnostics


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
CACHE_BUCKETS = ("posters", "backdrops", "subtitles")


@router.get("/playback", response_model=PlaybackDiagnosticsResponse)
def get_playback_diagnostics() -> dict:
    return playback_diagnostics()


@router.get("/cache", response_model=CacheDiagnosticsResponse)
def get_cache_diagnostics() -> dict:
    buckets = [_cache_bucket_diagnostics(name, MEDIA_CACHE_DIR / name) for name in CACHE_BUCKETS]
    return {
        "root": str(MEDIA_CACHE_DIR),
        "total_files": sum(bucket["files"] for bucket in buckets),
        "total_bytes": sum(bucket["bytes"] for bucket in buckets),
        "buckets": buckets,
    }


def _cache_bucket_diagnostics(name: str, path: Path) -> dict[str, Any]:
    files = 0
    bytes_used = 0
    extensions: dict[str, int] = {}
    if not path.exists():
        return {
            "name": name,
            "path": str(path),
            "exists": False,
            "files": 0,
            "bytes": 0,
            "extensions": {},
        }

    for child in path.rglob("*"):
        try:
            if not child.is_file():
                continue
            stat = child.stat()
        except OSError:
            continue
        files += 1
        bytes_used += stat.st_size
        extension = child.suffix.lower() or "[none]"
        extensions[extension] = extensions.get(extension, 0) + 1

    return {
        "name": name,
        "path": str(path),
        "exists": True,
        "files": files,
        "bytes": bytes_used,
        "extensions": dict(sorted(extensions.items())),
    }
