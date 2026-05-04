from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from app.config import ARTWORK_EXTENSIONS, VIDEO_EXTENSIONS
from app.services.library_service import LibraryService, utc_now
from app.services.metadata_service import MetadataService

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
    def __init__(self, library: LibraryService, metadata: Optional[MetadataService] = None) -> None:
        self.library = library
        self.metadata = metadata or MetadataService()

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

    def scan_sources(self, source_id: Optional[int] = None, limit: int = 5000) -> dict[str, Any]:
        sources = self.library.list_sources()
        if source_id is not None:
            sources = [source for source in sources if source["id"] == source_id]
            if not sources:
                raise FileNotFoundError(f"Media source does not exist: {source_id}")

        scanned_sources = 0
        skipped_sources = 0
        indexed_items = 0
        now = utc_now()

        for source in sources:
            if source.get("available") is False:
                skipped_sources += 1
                continue

            root = Path(source["path"])
            self.library.mark_source_media_unavailable(int(source["id"]))
            batch: list[dict[str, Any]] = []
            for media_path in self._walk_video_files(root):
                if indexed_items + len(batch) >= limit:
                    break
                try:
                    batch.append(
                        self._build_media_item(
                            media_path,
                            source_id=int(source["id"]),
                            source_path=str(root),
                            now=now,
                        )
                    )
                except OSError:
                    continue

            indexed_items += self.library.upsert_media_items(batch)
            scanned_sources += 1
            if indexed_items >= limit:
                break

        return {
            "sources_scanned": scanned_sources,
            "sources_skipped": skipped_sources,
            "items_indexed": indexed_items,
            "limit": limit,
        }

    def refresh_metadata(
        self,
        *,
        paths: Optional[list[str]] = None,
        source_id: Optional[int] = None,
        limit: int = 5000,
        force: bool = True,
    ) -> dict[str, Any]:
        if source_id is not None and self.library.get_source(source_id) is None:
            raise FileNotFoundError(f"Media source does not exist: {source_id}")

        requested_paths = self._normalize_refresh_paths(paths)[:limit] if paths is not None else None
        candidates = self.library.list_media_items_for_refresh(
            paths=requested_paths,
            source_id=source_id,
            limit=limit,
        )
        if requested_paths is not None:
            candidate_by_path = {str(candidate["path"]): candidate for candidate in candidates}
            missing_requested = [path for path in requested_paths if path not in candidate_by_path]
            candidates = [candidate_by_path[path] for path in requested_paths if path in candidate_by_path]
        else:
            missing_requested = []

        summary: dict[str, Any] = {
            "items_refreshed": 0,
            "items_missing": len(missing_requested),
            "items_skipped": len(missing_requested),
            "errors": [
                {"path": path, "error": "Media item is not indexed."}
                for path in missing_requested
            ],
            "limit": limit,
        }
        if not candidates:
            return summary

        now = utc_now()
        refresh_items: list[dict[str, Any]] = []
        unavailable_paths: list[str] = []

        for candidate in candidates:
            candidate_path = str(candidate["path"])
            media_path = Path(candidate_path).expanduser()
            try:
                if not media_path.exists() or not media_path.is_file():
                    unavailable_paths.append(candidate_path)
                    summary["items_missing"] += 1
                    summary["items_skipped"] += 1
                    continue
                if not self.is_video(media_path):
                    summary["items_skipped"] += 1
                    summary["errors"].append({"path": candidate_path, "error": "Path is not a video file."})
                    continue
                if (
                    not force
                    and candidate.get("metadata_updated_at")
                    and candidate.get("overview")
                    and candidate.get("poster_path")
                ):
                    summary["items_skipped"] += 1
                    continue
                refresh_items.append(
                    self._build_media_item(
                        media_path,
                        source_id=candidate.get("source_id"),
                        source_path=str(candidate.get("source_path") or media_path.parent),
                        now=now,
                    )
                )
            except OSError as exc:
                unavailable_paths.append(candidate_path)
                summary["items_missing"] += 1
                summary["items_skipped"] += 1
                summary["errors"].append({"path": candidate_path, "error": str(exc)})
            except Exception as exc:
                summary["items_skipped"] += 1
                summary["errors"].append({"path": candidate_path, "error": str(exc) or exc.__class__.__name__})

        if unavailable_paths:
            self.library.mark_media_items_unavailable(unavailable_paths)
        if refresh_items:
            summary["items_refreshed"] = self.library.upsert_media_items(refresh_items)

        return summary

    def _build_media_item(
        self,
        media_path: Path,
        *,
        source_id: Optional[int],
        source_path: str,
        now: str,
    ) -> dict[str, Any]:
        stat = media_path.stat()
        metadata = self.describe_media(media_path)
        generated = self.metadata.enrich(media_path, metadata)
        return {
            "path": str(media_path),
            "source_id": source_id,
            "source_path": source_path,
            "name": media_path.name,
            "title": generated.get("title") or metadata.get("display_title") or media_path.stem,
            "display_title": generated.get("display_title") or metadata.get("display_title"),
            "year": generated.get("year") or metadata.get("year"),
            "season": generated.get("season") or metadata.get("season"),
            "episode": generated.get("episode") or metadata.get("episode"),
            "quality": generated.get("quality") or metadata.get("quality"),
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "artwork_url": generated.get("artwork_url") or metadata.get("artwork_url"),
            "overview": generated.get("overview"),
            "poster_path": generated.get("poster_path"),
            "backdrop_url": generated.get("backdrop_url"),
            "tmdb_id": generated.get("tmdb_id"),
            "media_type": generated.get("media_type"),
            "metadata_source": generated.get("metadata_source"),
            "metadata_updated_at": generated.get("metadata_updated_at"),
            "available": 1,
            "last_seen_at": now,
        }

    def _browse_video_metadata(self, media_path: Path) -> dict[str, Any]:
        parsed = self.describe_media(media_path)
        indexed = self.library.list_media_items_for_refresh(paths=[str(media_path.resolve())], limit=1)
        if indexed:
            indexed_item = indexed[0]
            return {
                **parsed,
                "title": indexed_item.get("title") or parsed.get("display_title"),
                "display_title": indexed_item.get("display_title") or indexed_item.get("title") or parsed.get("display_title"),
                "year": indexed_item.get("year") or parsed.get("year"),
                "season": indexed_item.get("season") or parsed.get("season"),
                "episode": indexed_item.get("episode") or parsed.get("episode"),
                "quality": indexed_item.get("quality") or parsed.get("quality"),
                "artwork_url": indexed_item.get("artwork_url") or parsed.get("artwork_url"),
                "overview": indexed_item.get("overview"),
                "poster_path": indexed_item.get("poster_path"),
                "backdrop_url": indexed_item.get("backdrop_url"),
                "media_type": indexed_item.get("media_type"),
                "metadata_source": indexed_item.get("metadata_source"),
                "metadata_updated_at": indexed_item.get("metadata_updated_at"),
            }
        return self.metadata.local_metadata(media_path, parsed)

    def _normalize_refresh_paths(self, paths: Optional[list[str]]) -> list[str]:
        normalized: list[str] = []
        seen = set()
        for raw_path in paths or []:
            path = str(Path(raw_path).expanduser().resolve())
            if path not in seen:
                normalized.append(path)
                seen.add(path)
        return normalized

    def _walk_video_files(self, root: Path):
        stack = [root]
        while stack:
            directory = stack.pop()
            try:
                children = sorted(directory.iterdir(), key=lambda child: child.name.lower())
            except OSError:
                continue
            for child in children:
                if child.name.startswith("."):
                    continue
                if child.is_dir():
                    stack.append(child)
                elif child.is_file() and self.is_video(child):
                    yield child.resolve()

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
            metadata = self._browse_video_metadata(child) if is_video else {}
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
                    "title": metadata.get("title"),
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
                    "overview": metadata.get("overview"),
                    "poster_path": metadata.get("poster_path"),
                    "backdrop_url": metadata.get("backdrop_url"),
                    "media_type": metadata.get("media_type"),
                    "metadata_source": metadata.get("metadata_source"),
                    "metadata_updated_at": metadata.get("metadata_updated_at"),
                }
            )

        items.sort(key=lambda item: (item["kind"] != "directory", item["name"].lower()))
        parent = str(path.parent) if path.parent != path else None
        return {"path": str(path), "parent": parent, "items": items}

    def media_details(self, raw_path: str) -> dict[str, Any]:
        path = Path(raw_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file does not exist: {path}")
        if not path.is_file():
            raise IsADirectoryError(f"Path is not a media file: {path}")
        if not self.is_video(path):
            raise ValueError("Path is not a supported video file")

        stat = path.stat()
        metadata = self._browse_video_metadata(path)
        playback = self.library.get_playback(str(path))
        duration = float(playback["duration"]) if playback and playback["duration"] else 0
        position = float(playback["position"]) if playback and playback["position"] else 0
        progress: Optional[float] = None
        if duration > 0:
            progress = min(position / duration, 1)

        return {
            "name": path.name,
            "title": metadata.get("title"),
            "display_title": metadata.get("display_title"),
            "path": str(path),
            "kind": "video",
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "playable": True,
            "favorite": self.library.is_favorite(str(path)),
            "progress": progress,
            "duration": duration if duration > 0 else None,
            "position": position if position > 0 else None,
            "year": metadata.get("year"),
            "season": metadata.get("season"),
            "episode": metadata.get("episode"),
            "quality": metadata.get("quality"),
            "artwork_url": metadata.get("artwork_url"),
            "overview": metadata.get("overview"),
            "poster_path": metadata.get("poster_path"),
            "backdrop_url": metadata.get("backdrop_url"),
            "media_type": metadata.get("media_type"),
            "metadata_source": metadata.get("metadata_source"),
            "metadata_updated_at": metadata.get("metadata_updated_at"),
        }
