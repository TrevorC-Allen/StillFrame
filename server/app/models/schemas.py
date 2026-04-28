from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    ok: bool
    app: str
    version: str
    mpv_available: bool
    ffmpeg_available: bool
    mpv_path: Optional[str] = None
    ffmpeg_path: Optional[str] = None
    full_playback_available: bool = False
    install_hint: Optional[str] = None
    database_path: str


class SourceCreate(BaseModel):
    path: str
    name: Optional[str] = None


class MediaSource(BaseModel):
    id: int
    name: str
    path: str
    created_at: str
    available: bool = True
    status: str = "available"
    last_error: Optional[str] = None


class BrowseItem(BaseModel):
    name: str
    display_title: Optional[str] = None
    path: str
    kind: str = Field(pattern="^(directory|video|file)$")
    size: Optional[int] = None
    modified_at: Optional[float] = None
    playable: bool = False
    favorite: bool = False
    progress: Optional[float] = None
    duration: Optional[float] = None
    position: Optional[float] = None
    year: Optional[int] = None
    season: Optional[int] = None
    episode: Optional[int] = None
    quality: Optional[str] = None
    artwork_url: Optional[str] = None


class BrowseResponse(BaseModel):
    path: str
    parent: Optional[str]
    items: list[BrowseItem]


class SubtitleTrack(BaseModel):
    path: str
    title: str
    format: str
    language: Optional[str] = None
    encoding: Optional[str] = None


class AudioTrack(BaseModel):
    id: Any
    title: Optional[str] = None
    language: Optional[str] = None
    codec: Optional[str] = None


class PlayRequest(BaseModel):
    path: str
    resume: bool = True
    start_position: Optional[float] = None


class PlayerCommand(BaseModel):
    command: str
    value: Optional[Any] = None


class PlayerState(BaseModel):
    path: Optional[str] = None
    title: Optional[str] = None
    duration: float = 0
    position: float = 0
    paused: bool = False
    audio_tracks: list[dict[str, Any]] = []
    subtitle_tracks: list[dict[str, Any]] = []
    selected_audio: Optional[Any] = None
    selected_subtitle: Optional[Any] = None
    error: Optional[str] = None
    ended: bool = False
    running: bool = False


class FavoriteRequest(BaseModel):
    path: str
    title: Optional[str] = None
    favorite: bool = True


class PlaybackRecord(BaseModel):
    path: str
    title: str
    duration: float
    position: float
    paused: bool
    audio_track: Optional[str] = None
    subtitle_track: Optional[str] = None
    finished: bool
    updated_at: str


class PlaybackUpdate(BaseModel):
    path: str
    title: Optional[str] = None
    duration: float = 0
    position: float = 0
    paused: bool = False
    finished: bool = False


class SettingUpdate(BaseModel):
    key: str
    value: str
