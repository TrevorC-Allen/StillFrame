from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.config import VIDEO_EXTENSIONS
from app.models.schemas import PlayRequest, PlayerCommand, PlayerState
from app.services.library_service import title_from_path
from app.state import library_service, mpv_controller, subtitle_manager
from player.mpv_controller import MPVUnavailableError


router = APIRouter(tags=["player"])


@router.post("/play", response_model=PlayerState)
def play(payload: PlayRequest) -> dict:
    try:
        media_path = _resolve_play_path(payload.path)
        start_position = _start_position(payload, str(media_path))
        subtitles = subtitle_manager.match_subtitles(str(media_path))
        state = mpv_controller.open(
            str(media_path),
            start_position=start_position,
            subtitles=[subtitle["path"] for subtitle in subtitles],
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except MPVUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    _save_state(state)
    return state


@router.get("/player/state", response_model=PlayerState)
def player_state() -> dict:
    state = mpv_controller.get_state()
    _save_state(state)
    return state


@router.post("/player/command", response_model=PlayerState)
def player_command(payload: PlayerCommand) -> dict:
    try:
        if payload.command == "open":
            if not isinstance(payload.value, str):
                raise HTTPException(status_code=400, detail="open command requires a media path string")
            return play(PlayRequest(path=payload.value))
        state = mpv_controller.command(payload.command, payload.value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    _save_state(state)
    return state


@router.get("/subtitles")
def list_subtitles(media_path: str = Query(..., min_length=1)) -> list[dict]:
    try:
        return subtitle_manager.match_subtitles(media_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/subtitles/webvtt")
def subtitle_webvtt(
    path: str = Query(..., min_length=1),
    offset: float = Query(0, ge=-30, le=30),
) -> Response:
    try:
        webvtt = subtitle_manager.to_webvtt(path, offset=offset)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    return Response(
        content=webvtt,
        media_type="text/vtt; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


def _resolve_play_path(raw_path: str) -> Path:
    try:
        media_path = Path(raw_path).expanduser().resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"Invalid media path: {exc}") from exc
    if not media_path.exists():
        raise FileNotFoundError(f"Media file does not exist: {media_path}")
    if not media_path.is_file():
        raise ValueError(f"Media path is not a file: {media_path}")
    if media_path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise ValueError(f"Path is not a supported video file: {media_path}")
    return media_path


def _start_position(payload: PlayRequest, media_path: str) -> float:
    if payload.start_position is not None:
        return max(float(payload.start_position), 0)
    if not payload.resume:
        return 0

    playback = library_service.get_playback(media_path)
    if not playback:
        return 0
    duration = float(playback["duration"] or 0)
    position = float(playback["position"] or 0)
    if duration > 0 and position / duration > 0.95:
        return 0
    return max(position, 0)


def _save_state(state: dict) -> None:
    path = state.get("path")
    if not path:
        return
    duration = float(state.get("duration") or 0)
    position = float(state.get("position") or 0)
    finished = duration > 0 and position / duration > 0.95
    library_service.save_playback(
        path,
        title=state.get("title") or title_from_path(path),
        duration=duration,
        position=position,
        paused=bool(state.get("paused")),
        audio_track=str(state.get("selected_audio")) if state.get("selected_audio") is not None else None,
        subtitle_track=str(state.get("selected_subtitle")) if state.get("selected_subtitle") is not None else None,
        finished=finished or bool(state.get("ended")),
    )
