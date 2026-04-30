from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import LibraryScanRequest
from app.state import library_service, media_service


router = APIRouter(tags=["library"])


@router.get("/library")
def list_library(
    search: Optional[str] = Query(None, min_length=1),
    limit: int = Query(100, ge=1, le=500),
    sort: str = Query("title", pattern="^(title|recent|size|year)$"),
    include_unavailable: bool = Query(False),
) -> dict:
    items = library_service.list_media_items(
        search=search,
        limit=limit,
        sort=sort,
        include_unavailable=include_unavailable,
    )
    for item in items:
        item["available"] = bool(item["available"])
        item["favorite"] = bool(item["favorite"])
        item["finished"] = bool(item["finished"]) if item.get("finished") is not None else False
    return {"items": items, "total": len(items)}


@router.post("/library/scan")
def scan_library(payload: LibraryScanRequest) -> dict:
    try:
        return media_service.scan_sources(source_id=payload.source_id, limit=payload.limit)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
