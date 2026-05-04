from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.config import ARTWORK_EXTENSIONS, ROOT_DIR, VIDEO_EXTENSIONS


router = APIRouter(tags=["media"])
STATIC_DIR = ROOT_DIR / "server" / "app" / "static"


@router.get("/")
def web_app() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@router.get("/static/{asset_name}")
def static_asset(asset_name: str) -> FileResponse:
    path = STATIC_DIR / asset_name
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Static asset not found")
    return FileResponse(path)


@router.get("/media/stream")
def stream_media(
    path: str = Query(..., min_length=1),
    range_header: Optional[str] = Header(default=None, alias="Range"),
) -> Response:
    media_path = _resolve_requested_path(path, "media")
    if not media_path.exists() or not media_path.is_file():
        raise HTTPException(status_code=404, detail=f"Media file does not exist: {media_path}")
    if media_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Path is not a supported video file")

    file_size = media_path.stat().st_size
    media_type = mimetypes.guess_type(media_path.name)[0] or "application/octet-stream"

    if not range_header:
        return FileResponse(media_path, media_type=media_type)

    start, end = _parse_range(range_header, file_size)
    chunk_size = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Content-Length": str(chunk_size),
    }
    return StreamingResponse(
        _iter_file_range(media_path, start, end),
        status_code=206,
        media_type=media_type,
        headers=headers,
    )


@router.get("/media/artwork")
def media_artwork(path: str = Query(..., min_length=1)) -> FileResponse:
    artwork_path = _resolve_requested_path(path, "artwork")
    if not artwork_path.exists() or not artwork_path.is_file():
        raise HTTPException(status_code=404, detail="Artwork not found")
    if artwork_path.suffix.lower() not in ARTWORK_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported artwork file")
    media_type = mimetypes.guess_type(artwork_path.name)[0] or "image/jpeg"
    return FileResponse(artwork_path, media_type=media_type)


def _resolve_requested_path(raw_path: str, media_kind: str) -> Path:
    try:
        return Path(raw_path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {media_kind} path: {exc}") from exc


def _parse_range(range_header: str, file_size: int) -> tuple[int, int]:
    if not range_header.startswith("bytes="):
        raise HTTPException(status_code=416, detail="Invalid range header")

    try:
        raw_start, raw_end = range_header.removeprefix("bytes=").split("-", 1)
        if raw_start == "":
            if not raw_end:
                raise ValueError
            suffix_length = int(raw_end)
            if suffix_length <= 0:
                raise ValueError
            start = max(file_size - suffix_length, 0)
            end = file_size - 1
        else:
            start = int(raw_start)
            end = int(raw_end) if raw_end else file_size - 1
    except ValueError as exc:
        raise HTTPException(status_code=416, detail="Invalid range header") from exc

    if start >= file_size or end < start:
        raise HTTPException(status_code=416, detail="Requested range not satisfiable")

    return start, min(end, file_size - 1)


def _iter_file_range(path: Path, start: int, end: int):
    with path.open("rb") as handle:
        handle.seek(start)
        remaining = end - start + 1
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
