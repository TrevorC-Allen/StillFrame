from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.models.schemas import (
    LibraryMetadataRefreshRequest,
    LibraryMetadataRefreshResponse,
    LibraryScanJob,
    LibraryScanJobsResponse,
    LibraryScanRequest,
)
from app.state import library_service, media_service


router = APIRouter(tags=["library"])


def _run_scan_job(job_id: int, source_id: Optional[int], limit: int) -> None:
    try:
        summary = media_service.scan_sources(source_id=source_id, limit=limit)
    except Exception as exc:
        message = str(exc) or exc.__class__.__name__
        library_service.fail_scan_job(job_id, message)
        return

    library_service.complete_scan_job(job_id, summary)


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
def scan_library(
    background_tasks: BackgroundTasks,
    payload: Optional[LibraryScanRequest] = None,
    synchronous: Optional[bool] = Query(None),
    wait: Optional[bool] = Query(None),
) -> dict:
    payload = payload or LibraryScanRequest()
    run_synchronously = bool(payload.synchronous or payload.wait or synchronous or wait)
    try:
        if run_synchronously:
            return media_service.scan_sources(source_id=payload.source_id, limit=payload.limit)

        job = library_service.create_scan_job(source_id=payload.source_id, limit=payload.limit)
        background_tasks.add_task(_run_scan_job, int(job["id"]), payload.source_id, payload.limit)
        return job
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/library/metadata/refresh", response_model=LibraryMetadataRefreshResponse)
def refresh_library_metadata(payload: Optional[LibraryMetadataRefreshRequest] = None) -> dict:
    payload = payload or LibraryMetadataRefreshRequest()
    try:
        return media_service.refresh_metadata(
            paths=payload.paths,
            source_id=payload.source_id,
            limit=payload.limit,
            force=payload.force,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/library/scan/jobs", response_model=LibraryScanJobsResponse)
def list_scan_jobs(limit: int = Query(20, ge=1, le=100)) -> dict:
    jobs = library_service.list_scan_jobs(limit=limit)
    return {"items": jobs, "total": len(jobs)}


@router.get("/library/scan/jobs/{job_id}", response_model=LibraryScanJob)
def get_scan_job(job_id: int) -> dict:
    job = library_service.get_scan_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Scan job does not exist: {job_id}")
    return job
