from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import MEDIA_CACHE_DIR
from app.models.schemas import CacheClearResponse, CacheDiagnosticsResponse, PlaybackDiagnosticsResponse
from app.state import playback_diagnostics


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])
CACHE_BUCKETS = ("posters", "backdrops", "subtitles")


@router.get("/playback", response_model=PlaybackDiagnosticsResponse)
def get_playback_diagnostics() -> dict:
    return playback_diagnostics()


@router.get("/cache", response_model=CacheDiagnosticsResponse)
def get_cache_diagnostics() -> dict:
    return _cache_diagnostics()


@router.post("/cache/clear", response_model=CacheClearResponse)
def clear_cache(bucket: str = Query("all", pattern="^(all|posters|backdrops|subtitles)$")) -> dict:
    targets = CACHE_BUCKETS if bucket == "all" else (bucket,)
    removed_files = 0
    removed_bytes = 0
    for name in targets:
        result = _clear_cache_bucket(MEDIA_CACHE_DIR / name)
        removed_files += result["files"]
        removed_bytes += result["bytes"]

    diagnostics = _cache_diagnostics()
    return {
        **diagnostics,
        "removed_files": removed_files,
        "removed_bytes": removed_bytes,
    }


def _cache_diagnostics() -> dict:
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


def _clear_cache_bucket(path: Path) -> dict[str, int]:
    try:
        resolved_root = MEDIA_CACHE_DIR.resolve()
        resolved_path = path.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid cache path: {exc}") from exc

    if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="Refusing to clear path outside StillFrame media cache")
    if not path.exists():
        return {"files": 0, "bytes": 0}

    removed_files = 0
    removed_bytes = 0
    for child in path.rglob("*"):
        try:
            if not child.is_file():
                continue
            size = child.stat().st_size
            child.unlink()
        except OSError:
            continue
        removed_files += 1
        removed_bytes += size
    return {"files": removed_files, "bytes": removed_bytes}
