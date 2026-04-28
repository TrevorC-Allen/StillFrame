from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import FavoriteRequest
from app.state import library_service, media_service


router = APIRouter(tags=["favorites"])


@router.get("/favorites")
def list_favorites() -> list[dict]:
    return [media_service.enrich_record(record) for record in library_service.list_favorites()]


@router.post("/favorites")
def set_favorite(payload: FavoriteRequest) -> dict:
    favorite = library_service.set_favorite(
        payload.path,
        favorite=payload.favorite,
        title=payload.title,
    )
    return {"path": payload.path, "favorite": favorite}
