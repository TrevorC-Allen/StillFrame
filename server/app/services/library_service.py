from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.database import Database


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
