from __future__ import annotations

from fastapi import APIRouter, Query

from app.models.schemas import PlaybackUpdate
from app.state import library_service, media_service


router = APIRouter(tags=["history"])


@router.get("/history")
def list_history(limit: int = Query(50, ge=1, le=200)) -> list[dict]:
    records = library_service.list_history(limit=limit)
    for record in records:
        record["paused"] = bool(record["paused"])
        record["finished"] = bool(record["finished"])
    return [media_service.enrich_record(record) for record in records]


@router.post("/history/progress")
def save_progress(payload: PlaybackUpdate) -> dict:
    record = library_service.save_playback(
        payload.path,
        title=payload.title,
        duration=payload.duration,
        position=payload.position,
        paused=payload.paused,
        finished=payload.finished,
    )
    record["paused"] = bool(record["paused"])
    record["finished"] = bool(record["finished"])
    return media_service.enrich_record(record)


@router.post("/history/clear")
def clear_history() -> dict:
    deleted = library_service.clear_history()
    return {"deleted": deleted}
