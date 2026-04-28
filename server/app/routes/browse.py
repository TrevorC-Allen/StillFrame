from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import BrowseResponse
from app.state import media_service


router = APIRouter(tags=["browse"])


@router.get("/browse", response_model=BrowseResponse)
def browse(path: str = Query(..., min_length=1)) -> dict:
    try:
        return media_service.browse(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except NotADirectoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

