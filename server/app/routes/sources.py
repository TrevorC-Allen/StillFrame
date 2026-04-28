from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.schemas import MediaSource, SourceCreate
from app.state import library_service


router = APIRouter(tags=["sources"])


@router.get("/sources", response_model=list[MediaSource])
def list_sources() -> list[dict]:
    return library_service.list_sources()


@router.post("/sources", response_model=MediaSource)
def add_source(payload: SourceCreate) -> dict:
    path = Path(payload.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Source path does not exist: {path}")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Source path is not a directory: {path}")
    return library_service.add_source(str(path), payload.name)


@router.delete("/sources/{source_id}")
def delete_source(source_id: int) -> dict:
    library_service.delete_source(source_id)
    return {"deleted": source_id}

