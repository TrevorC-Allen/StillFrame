from __future__ import annotations

from fastapi import APIRouter

from app.models.schemas import PlaybackDiagnosticsResponse
from app.state import playback_diagnostics


router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/playback", response_model=PlaybackDiagnosticsResponse)
def get_playback_diagnostics() -> dict:
    return playback_diagnostics()
