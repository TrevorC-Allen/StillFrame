from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.database import Database


MEDIA_TYPE_LABELS = {
    "movie": "Movie",
    "tv": "TV",
    "unknown": "Unknown",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def title_from_path(path: str) -> str:
    return Path(path).stem or Path(path).name or path


class LibraryService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_sources(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT id, name, path, created_at FROM sources ORDER BY name COLLATE NOCASE"
            ).fetchall()
        return [self._with_source_status(dict(row)) for row in rows]

    def get_source(self, source_id: int) -> Optional[dict[str, Any]]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, name, path, created_at FROM sources WHERE id = ?",
                (source_id,),
            ).fetchone()
        return self._with_source_status(dict(row)) if row else None

    def add_source(self, path: str, name: Optional[str] = None) -> dict[str, Any]:
        resolved = str(Path(path).expanduser().resolve())
        source_name = name or Path(resolved).name or resolved
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sources (name, path, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET name = excluded.name
                """,
                (source_name, resolved, now),
            )
            row = connection.execute(
                "SELECT id, name, path, created_at FROM sources WHERE path = ?",
                (resolved,),
            ).fetchone()
        return self._with_source_status(dict(row))

    def delete_source(self, source_id: int) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))

    def _with_source_status(self, source: dict[str, Any]) -> dict[str, Any]:
        path = Path(source["path"])
        try:
            if not path.exists():
                return {
                    **source,
                    "available": False,
                    "status": "missing",
                    "last_error": "Source is disconnected or no longer exists.",
                }
            if not path.is_dir():
                return {
                    **source,
                    "available": False,
                    "status": "not_directory",
                    "last_error": "Source path is no longer a folder.",
                }
            next(path.iterdir(), None)
        except PermissionError:
            return {
                **source,
                "available": False,
                "status": "permission_denied",
                "last_error": "StillFrame cannot read this folder. Check Finder privacy permissions.",
            }
        except OSError as exc:
            return {
                **source,
                "available": False,
                "status": "error",
                "last_error": str(exc),
            }

        return {
            **source,
            "available": True,
            "status": "available",
            "last_error": None,
        }

    def mark_source_media_unavailable(self, source_id: int) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE media_items SET available = 0 WHERE source_id = ?",
                (source_id,),
            )
        return int(cursor.rowcount or 0)

    def mark_media_items_unavailable(self, paths: list[str]) -> int:
        if not paths:
            return 0

        with self.database.connect() as connection:
            cursor = connection.executemany(
                "UPDATE media_items SET available = 0 WHERE path = ?",
                ((path,) for path in paths),
            )
        return int(cursor.rowcount or 0)

    def create_scan_job(self, *, source_id: Optional[int] = None, limit: int = 5000) -> dict[str, Any]:
        now = utc_now()
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO scan_jobs (
                    status, source_id, "limit", items_indexed, sources_scanned,
                    sources_skipped, error, started_at, completed_at
                )
                VALUES (?, ?, ?, 0, 0, 0, NULL, ?, NULL)
                """,
                ("running", source_id, limit, now),
            )
            row = self._get_scan_job_row(connection, int(cursor.lastrowid))
        return dict(row)

    def complete_scan_job(self, job_id: int, summary: dict[str, Any]) -> dict[str, Any]:
        completed_at = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE scan_jobs
                SET
                    status = ?,
                    items_indexed = ?,
                    sources_scanned = ?,
                    sources_skipped = ?,
                    error = NULL,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    "completed",
                    int(summary.get("items_indexed") or 0),
                    int(summary.get("sources_scanned") or 0),
                    int(summary.get("sources_skipped") or 0),
                    completed_at,
                    job_id,
                ),
            )
            row = self._get_scan_job_row(connection, job_id)
        return dict(row)

    def fail_scan_job(self, job_id: int, error: str) -> dict[str, Any]:
        completed_at = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE scan_jobs
                SET status = ?, error = ?, completed_at = ?
                WHERE id = ?
                """,
                ("failed", error, completed_at, job_id),
            )
            row = self._get_scan_job_row(connection, job_id)
        return dict(row)

    def get_scan_job(self, job_id: int) -> Optional[dict[str, Any]]:
        with self.database.connect() as connection:
            row = self._get_scan_job_row(connection, job_id)
        return dict(row) if row else None

    def list_scan_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    id, status, source_id, "limit", items_indexed,
                    sources_scanned, sources_skipped, error, started_at, completed_at
                FROM scan_jobs
                ORDER BY started_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _get_scan_job_row(self, connection: Any, job_id: int) -> Any:
        return connection.execute(
            """
            SELECT
                id, status, source_id, "limit", items_indexed,
                sources_scanned, sources_skipped, error, started_at, completed_at
            FROM scan_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    def upsert_media_items(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0

        with self.database.connect() as connection:
            connection.executemany(
                """
                INSERT INTO media_items (
                    path, source_id, source_path, name, title, display_title,
                    year, season, episode, quality, size, modified_at,
                    artwork_url, overview, poster_path, backdrop_url, tmdb_id,
                    media_type, metadata_source, metadata_updated_at, available,
                    last_seen_at
                )
                VALUES (
                    :path, :source_id, :source_path, :name, :title, :display_title,
                    :year, :season, :episode, :quality, :size, :modified_at,
                    :artwork_url, :overview, :poster_path, :backdrop_url, :tmdb_id,
                    :media_type, :metadata_source, :metadata_updated_at, :available,
                    :last_seen_at
                )
                ON CONFLICT(path) DO UPDATE SET
                    source_id = excluded.source_id,
                    source_path = excluded.source_path,
                    name = excluded.name,
                    title = excluded.title,
                    display_title = excluded.display_title,
                    year = excluded.year,
                    season = excluded.season,
                    episode = excluded.episode,
                    quality = excluded.quality,
                    size = excluded.size,
                    modified_at = excluded.modified_at,
                    artwork_url = excluded.artwork_url,
                    overview = excluded.overview,
                    poster_path = excluded.poster_path,
                    backdrop_url = excluded.backdrop_url,
                    tmdb_id = excluded.tmdb_id,
                    media_type = excluded.media_type,
                    metadata_source = excluded.metadata_source,
                    metadata_updated_at = excluded.metadata_updated_at,
                    available = excluded.available,
                    last_seen_at = excluded.last_seen_at
                """,
                items,
            )
        return len(items)

    def list_media_items(
        self,
        *,
        search: Optional[str] = None,
        limit: int = 100,
        sort: str = "title",
        include_unavailable: bool = False,
        media_type: Optional[str] = None,
        year: Optional[int] = None,
        quality: Optional[str] = None,
        source_id: Optional[int] = None,
        favorite: Optional[bool] = None,
        available: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        sort_sql = {
            "title": "LOWER(media_items.title) ASC, media_items.name ASC",
            "recent": "media_items.modified_at DESC, LOWER(media_items.title) ASC",
            "size": "media_items.size DESC, LOWER(media_items.title) ASC",
            "year": "media_items.year DESC, LOWER(media_items.title) ASC",
        }.get(sort, "LOWER(media_items.title) ASC, media_items.name ASC")

        clauses, params = self._library_filter_clauses(
            search=search,
            include_unavailable=include_unavailable,
            media_type=media_type,
            year=year,
            quality=quality,
            source_id=source_id,
            favorite=favorite,
            available=available,
        )
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT
                    media_items.*,
                    playback_states.duration,
                    playback_states.position,
                    playback_states.finished,
                    CASE WHEN favorites.path IS NULL THEN 0 ELSE 1 END AS favorite
                FROM media_items
                LEFT JOIN playback_states ON playback_states.path = media_items.path
                LEFT JOIN favorites ON favorites.path = media_items.path
                {where_sql}
                ORDER BY {sort_sql}
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def library_facets(self) -> dict[str, Any]:
        with self.database.connect() as connection:
            stats = connection.execute(
                """
                SELECT
                    COUNT(media_items.path) AS total,
                    COALESCE(SUM(CASE WHEN media_items.available = 1 THEN 1 ELSE 0 END), 0) AS available,
                    COALESCE(SUM(CASE WHEN media_items.available = 0 THEN 1 ELSE 0 END), 0) AS offline,
                    COALESCE(SUM(CASE WHEN favorites.path IS NULL THEN 0 ELSE 1 END), 0) AS favorites
                FROM media_items
                LEFT JOIN favorites ON favorites.path = media_items.path
                """
            ).fetchone()
            media_type_rows = connection.execute(
                """
                SELECT
                    LOWER(COALESCE(NULLIF(TRIM(media_type), ''), 'unknown')) AS value,
                    COUNT(*) AS count
                FROM media_items
                GROUP BY value
                ORDER BY count DESC, value ASC
                """
            ).fetchall()
            year_rows = connection.execute(
                """
                SELECT year AS value, COUNT(*) AS count
                FROM media_items
                WHERE year IS NOT NULL
                GROUP BY year
                ORDER BY year DESC
                """
            ).fetchall()
            quality_rows = connection.execute(
                """
                SELECT UPPER(TRIM(quality)) AS value, COUNT(*) AS count
                FROM media_items
                WHERE quality IS NOT NULL AND TRIM(quality) != ''
                GROUP BY value
                ORDER BY count DESC, value COLLATE NOCASE ASC
                """
            ).fetchall()
            source_rows = connection.execute(
                """
                SELECT
                    sources.id,
                    sources.name,
                    sources.path,
                    sources.created_at,
                    COUNT(media_items.path) AS count
                FROM sources
                LEFT JOIN media_items ON media_items.source_id = sources.id
                GROUP BY sources.id, sources.name, sources.path, sources.created_at
                ORDER BY sources.name COLLATE NOCASE ASC
                """
            ).fetchall()

        return {
            "total": int(stats["total"] or 0),
            "available": int(stats["available"] or 0),
            "offline": int(stats["offline"] or 0),
            "favorites": int(stats["favorites"] or 0),
            "media_types": [
                {
                    "value": row["value"],
                    "label": self._media_type_label(row["value"]),
                    "count": int(row["count"] or 0),
                }
                for row in media_type_rows
            ],
            "years": [
                {"value": int(row["value"]), "count": int(row["count"] or 0)}
                for row in year_rows
            ],
            "qualities": [
                {"value": row["value"], "count": int(row["count"] or 0)}
                for row in quality_rows
            ],
            "sources": [
                {
                    "id": int(source["id"]),
                    "name": source["name"],
                    "path": source["path"],
                    "count": int(source["count"] or 0),
                    "available": bool(source["available"]),
                }
                for source in (self._with_source_status(dict(row)) for row in source_rows)
            ],
        }

    def _library_filter_clauses(
        self,
        *,
        search: Optional[str] = None,
        include_unavailable: bool = False,
        media_type: Optional[str] = None,
        year: Optional[int] = None,
        quality: Optional[str] = None,
        source_id: Optional[int] = None,
        favorite: Optional[bool] = None,
        available: Optional[bool] = None,
    ) -> tuple[list[str], list[Any]]:
        clauses = []
        params: list[Any] = []
        if available is not None:
            clauses.append("media_items.available = ?")
            params.append(1 if available else 0)
        elif not include_unavailable:
            clauses.append("media_items.available = 1")
        if search:
            clauses.append(
                """
                (
                    media_items.title LIKE ?
                    OR media_items.display_title LIKE ?
                    OR media_items.name LIKE ?
                    OR media_items.source_path LIKE ?
                )
                """
            )
            needle = f"%{search}%"
            params.extend([needle, needle, needle, needle])
        if media_type:
            if media_type.lower() == "unknown":
                clauses.append("(media_items.media_type IS NULL OR TRIM(media_items.media_type) = '')")
            else:
                clauses.append("LOWER(media_items.media_type) = LOWER(?)")
                params.append(media_type)
        if year is not None:
            clauses.append("media_items.year = ?")
            params.append(year)
        if quality:
            clauses.append("LOWER(media_items.quality) = LOWER(?)")
            params.append(quality)
        if source_id is not None:
            clauses.append("media_items.source_id = ?")
            params.append(source_id)
        if favorite is not None:
            clauses.append("favorites.path IS NOT NULL" if favorite else "favorites.path IS NULL")
        return clauses, params

    def _media_type_label(self, value: str) -> str:
        return MEDIA_TYPE_LABELS.get(value, value.replace("_", " ").title())

    def list_media_items_for_refresh(
        self,
        *,
        paths: Optional[list[str]] = None,
        source_id: Optional[int] = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        if paths is not None:
            if not paths:
                return []

            rows: list[dict[str, Any]] = []
            with self.database.connect() as connection:
                for index in range(0, len(paths), 900):
                    chunk = paths[index : index + 900]
                    placeholders = ", ".join("?" for _ in chunk)
                    clauses = [f"path IN ({placeholders})"]
                    params: list[Any] = list(chunk)
                    if source_id is not None:
                        clauses.append("source_id = ?")
                        params.append(source_id)
                    rows.extend(
                        dict(row)
                        for row in connection.execute(
                            f"""
                            SELECT *
                            FROM media_items
                            WHERE {' AND '.join(clauses)}
                            """,
                            params,
                        ).fetchall()
                    )
            return rows[:limit]

        clauses = []
        params: list[Any] = []
        if source_id is not None:
            clauses.append("source_id = ?")
            params.append(source_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM media_items
                {where_sql}
                ORDER BY LOWER(title) ASC, name ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_playback(self, path: str) -> Optional[dict[str, Any]]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM playback_states WHERE path = ?",
                (path,),
            ).fetchone()
        return dict(row) if row else None

    def save_playback(
        self,
        path: str,
        *,
        title: Optional[str] = None,
        duration: float = 0,
        position: float = 0,
        paused: bool = False,
        audio_track: Optional[str] = None,
        subtitle_track: Optional[str] = None,
        finished: bool = False,
    ) -> dict[str, Any]:
        media_title = title or title_from_path(path)
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO playback_states (
                    path, title, duration, position, paused, audio_track,
                    subtitle_track, finished, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    title = excluded.title,
                    duration = excluded.duration,
                    position = excluded.position,
                    paused = excluded.paused,
                    audio_track = excluded.audio_track,
                    subtitle_track = excluded.subtitle_track,
                    finished = excluded.finished,
                    updated_at = excluded.updated_at
                """,
                (
                    path,
                    media_title,
                    float(duration or 0),
                    float(position or 0),
                    1 if paused else 0,
                    audio_track,
                    subtitle_track,
                    1 if finished else 0,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM playback_states WHERE path = ?",
                (path,),
            ).fetchone()
        return dict(row)

    def list_history(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM playback_states
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def clear_history(self) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute("DELETE FROM playback_states")
        return int(cursor.rowcount or 0)

    def set_favorite(self, path: str, favorite: bool = True, title: Optional[str] = None) -> bool:
        if favorite:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO favorites (path, title, created_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(path) DO UPDATE SET title = excluded.title
                    """,
                    (path, title or title_from_path(path), utc_now()),
                )
            return True

        with self.database.connect() as connection:
            connection.execute("DELETE FROM favorites WHERE path = ?", (path,))
        return False

    def is_favorite(self, path: str) -> bool:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT path FROM favorites WHERE path = ?",
                (path,),
            ).fetchone()
        return row is not None

    def list_favorites(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT path, title, created_at FROM favorites ORDER BY created_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def set_setting(self, key: str, value: str) -> dict[str, str]:
        now = utc_now()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )
        return {"key": key, "value": value}

    def get_settings(self) -> dict[str, str]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}
