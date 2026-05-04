from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS playback_states (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    duration REAL NOT NULL DEFAULT 0,
    position REAL NOT NULL DEFAULT 0,
    paused INTEGER NOT NULL DEFAULT 0,
    audio_track TEXT,
    subtitle_track TEXT,
    finished INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorites (
    path TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media_items (
    path TEXT PRIMARY KEY,
    source_id INTEGER,
    source_path TEXT NOT NULL,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    display_title TEXT,
    year INTEGER,
    season INTEGER,
    episode INTEGER,
    quality TEXT,
    size INTEGER,
    modified_at REAL,
    artwork_url TEXT,
    overview TEXT,
    poster_path TEXT,
    backdrop_url TEXT,
    tmdb_id INTEGER,
    media_type TEXT,
    metadata_source TEXT,
    metadata_updated_at TEXT,
    available INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_media_items_source_id ON media_items(source_id);
CREATE INDEX IF NOT EXISTS idx_media_items_title ON media_items(title COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_media_items_modified_at ON media_items(modified_at);

CREATE TABLE IF NOT EXISTS scan_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    status TEXT NOT NULL,
    source_id INTEGER,
    "limit" INTEGER NOT NULL,
    items_indexed INTEGER NOT NULL DEFAULT 0,
    sources_scanned INTEGER NOT NULL DEFAULT 0,
    sources_skipped INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_jobs_started_at ON scan_jobs(started_at);
CREATE INDEX IF NOT EXISTS idx_scan_jobs_status ON scan_jobs(status);
"""


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            self._migrate_media_items(connection)

    def _migrate_media_items(self, connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(media_items)").fetchall()
        }
        additions = {
            "overview": "TEXT",
            "poster_path": "TEXT",
            "backdrop_url": "TEXT",
            "tmdb_id": "INTEGER",
            "media_type": "TEXT",
            "metadata_source": "TEXT",
            "metadata_updated_at": "TEXT",
        }
        for name, column_type in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE media_items ADD COLUMN {name} {column_type}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()
