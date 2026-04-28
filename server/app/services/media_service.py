from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from app.config import ARTWORK_EXTENSIONS, VIDEO_EXTENSIONS
from app.services.library_service import LibraryService

QUALITY_PATTERN = re.compile(r"\b(2160p|4k|1080p|720p|480p|hdr10\+?|dolby[ ._-]?vision|dv|webrip|bluray|bdrip)\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(?:^|[ ._\-\[(])((?:19|20)\d{2})(?:[ ._\-\])]|$)")
EPISODE_PATTERN = re.compile(r"\bS(\d{1,2})E(\d{1,3})\b", re.IGNORECASE)
TRASH_TOKENS = {
    "2160p",
    "4k",
    "1080p",
    "720p",
    "480p",
    "hdr",
    "hdr10",
    "hdr10plus",
    "dv",
    "dolby",
    "vision",
    "bluray",
    "bdrip",
    "webrip",
    "web",
    "dl",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "av1",
    "aac",
    "dts",
    "atmos",
    "truehd",
}


class MediaService:
    def __init__(self, library: LibraryService) -> None:
        self.library = library

    def is_video(self, path: Path) -> bool:
        return path.suffix.lower() in VIDEO_EXTENSIONS

    def describe_media(self, path: Path) -> dict[str, Any]:
        stem = path.stem
        episode_match = EPISODE_PATTERN.search(stem)
        year_match = YEAR_PATTERN.search(stem)
        quality_match = QUALITY_PATTERN.search(stem)

        title_area = stem[: year_match.start(1) if year_match else len(stem)]
        if episode_match and episode_match.start() < len(title_area):
            title_area = stem[: episode_match.start()]

        tokens = re.split(r"[ ._\-\[\]()]+", title_area)
        clean_tokens = [token for token in tokens if token and token.lower() not in TRASH_TOKENS]
        display_title = " ".join(clean_tokens).strip() or path.stem

        return {
            "display_title": display_title,
            "year": int(year_match.group(1)) if year_match else None,
            "season": int(episode_match.group(1)) if episode_match else None,
            "episode": int(episode_match.group(2)) if episode_match else None,
            "quality": quality_match.group(1).upper().replace("DOLBY VISION", "DV") if quality_match else None,
            "artwork_url": self.artwork_url(path),
        }

    def enrich_record(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        path = Path(str(record.get("path", ""))).expanduser()
        try:
            if not path.exists() or not path.is_file():
                enriched["media_available"] = False
                return enriched
            enriched["media_available"] = True
            if self.is_video(path):
                enriched.update(self.describe_media(path))
        except OSError as exc:
            enriched["media_available"] = False
            enriched["last_error"] = str(exc)
        return enriched

    def artwork_url(self, path: Path) -> Optional[str]:
        artwork = self.find_artwork(path)
        if not artwork:
            return None
        return f"/media/artwork?path={artwork}"

    def find_artwork(self, media_path: Path) -> Optional[Path]:
        base = media_path.with_suffix("")
        candidates = []
        for extension in ARTWORK_EXTENSIONS:
            candidates.extend(
                [
                    base.with_name(f"{base.name}-poster{extension}"),
                    base.with_name(f"{base.name}.poster{extension}"),
                    base.with_name(f"{base.name}{extension}"),
                ]
            )
        for name in ("poster", "cover", "folder"):
            candidates.extend(media_path.parent / f"{name}{extension}" for extension in ARTWORK_EXTENSIONS)

        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    def browse(self, raw_path: str) -> dict[str, Any]:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")
        if not path.is_dir():
            raise NotADirectoryError(f"Path is not a directory: {path}")

        items: list[dict[str, Any]] = []
        for child in path.iterdir():
            if child.name.startswith("."):
                continue
            try:
                stat = child.stat()
            except OSError:
                continue

            is_directory = child.is_dir()
            is_video = child.is_file() and self.is_video(child)
            if not is_directory and not is_video:
                continue

            child_path = str(child)
            metadata = self.describe_media(child) if is_video else {}
            playback = self.library.get_playback(child_path) if is_video else None
            duration = float(playback["duration"]) if playback and playback["duration"] else 0
            position = float(playback["position"]) if playback and playback["position"] else 0
            progress: Optional[float] = None
            if duration > 0:
                progress = min(position / duration, 1)

            items.append(
                {
                    "name": child.name,
                    "display_title": metadata.get("display_title"),
                    "path": child_path,
                    "kind": "directory" if is_directory else "video",
                    "size": None if is_directory else stat.st_size,
                    "modified_at": stat.st_mtime,
                    "playable": is_video,
                    "favorite": self.library.is_favorite(child_path) if is_video else False,
                    "progress": progress,
                    "duration": duration if duration > 0 else None,
                    "position": position if position > 0 else None,
                    "year": metadata.get("year"),
                    "season": metadata.get("season"),
                    "episode": metadata.get("episode"),
                    "quality": metadata.get("quality"),
                    "artwork_url": metadata.get("artwork_url"),
                }
            )

        items.sort(key=lambda item: (item["kind"] != "directory", item["name"].lower()))
        parent = str(path.parent) if path.parent != path else None
        return {"path": str(path), "parent": parent, "items": items}
