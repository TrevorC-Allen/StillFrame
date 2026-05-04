from __future__ import annotations

import sqlite3
import subprocess
from pathlib import Path

import pytest

from app.database import Database
from app.services import metadata_service as metadata_module
from app.services.library_service import LibraryService
from app.services.media_service import MediaService
from player.mpv_controller import MPVController, MPVUnavailableError
from player.subtitle_manager import SubtitleManager


def make_services(tmp_path: Path) -> tuple[LibraryService, MediaService]:
    database = Database(tmp_path / "stillframe-test.db")
    database.initialize()
    library = LibraryService(database)
    return library, MediaService(library)


def disable_tmdb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metadata_module, "TMDB_API_KEY", None)
    monkeypatch.setattr(metadata_module, "TMDB_BEARER_TOKEN", None)


def seed_indexed_media_item(
    library: LibraryService,
    media_path: Path,
    source: dict,
    *,
    title: str = "Stale Title",
    year: int | None = None,
    quality: str | None = None,
    media_type: str | None = None,
    available: int = 1,
) -> None:
    stat = media_path.stat()
    library.upsert_media_items(
        [
            {
                "path": str(media_path.resolve()),
                "source_id": int(source["id"]),
                "source_path": source["path"],
                "name": media_path.name,
                "title": title,
                "display_title": title,
                "year": year,
                "season": None,
                "episode": None,
                "quality": quality,
                "size": stat.st_size,
                "modified_at": stat.st_mtime,
                "artwork_url": None,
                "overview": "stale overview",
                "poster_path": None,
                "backdrop_url": None,
                "tmdb_id": None,
                "media_type": media_type,
                "metadata_source": "stale",
                "metadata_updated_at": "2025-01-01T00:00:00+00:00",
                "available": available,
                "last_seen_at": "2025-01-01T00:00:00+00:00",
            }
        ]
    )


def indexed_item_by_path(library: LibraryService, media_path: Path) -> dict:
    return next(
        item
        for item in library.list_media_items(limit=100, include_unavailable=True)
        if item["path"] == str(media_path.resolve())
    )


def test_database_sources_history_and_favorites(tmp_path: Path) -> None:
    library, _ = make_services(tmp_path)
    movie = tmp_path / "Movie.mkv"
    movie.write_text("fake video", encoding="utf-8")

    source = library.add_source(str(tmp_path))
    assert source["name"] == tmp_path.name
    assert source["available"] is True

    library.save_playback(str(movie), duration=100, position=25, paused=True)
    history = library.list_history()
    assert history[0]["path"] == str(movie)
    assert history[0]["position"] == 25
    assert library.clear_history() == 1
    assert library.list_history() == []

    assert library.set_favorite(str(movie), True) is True
    assert library.is_favorite(str(movie)) is True
    assert library.set_favorite(str(movie), False) is False
    assert library.is_favorite(str(movie)) is False


def test_sources_report_disconnected_paths(tmp_path: Path) -> None:
    library, _ = make_services(tmp_path)
    disconnected = tmp_path / "MountedNAS"
    disconnected.mkdir()
    source = library.add_source(str(disconnected))
    assert source["available"] is True

    disconnected.rmdir()
    sources = library.list_sources()

    assert sources[0]["path"] == str(disconnected)
    assert sources[0]["available"] is False
    assert sources[0]["status"] == "missing"
    assert "disconnected" in sources[0]["last_error"]


def test_browse_filters_to_directories_and_videos(tmp_path: Path) -> None:
    library, media = make_services(tmp_path)
    movie = tmp_path / "Arrival.2016.2160p.BluRay.HEVC.mkv"
    movie.write_text("fake video", encoding="utf-8")
    (tmp_path / "Notes.txt").write_text("not media", encoding="utf-8")
    (tmp_path / "Season 1").mkdir()
    library.save_playback(str(movie), duration=100, position=50)
    library.set_favorite(str(movie), True)

    result = media.browse(str(tmp_path))
    names = [item["name"] for item in result["items"]]

    assert "Season 1" in names
    assert "Arrival.2016.2160p.BluRay.HEVC.mkv" in names
    assert "Notes.txt" not in names

    movie_item = next(item for item in result["items"] if item["name"] == "Arrival.2016.2160p.BluRay.HEVC.mkv")
    assert movie_item["playable"] is True
    assert movie_item["favorite"] is True
    assert movie_item["progress"] == 0.5
    assert movie_item["duration"] == 100
    assert movie_item["position"] == 50
    assert movie_item["display_title"] == "Arrival"
    assert movie_item["year"] == 2016
    assert movie_item["quality"] == "2160P"


def test_local_artwork_discovery(tmp_path: Path) -> None:
    _, media = make_services(tmp_path)
    movie = tmp_path / "Movie.2024.mkv"
    poster = tmp_path / "Movie.2024-poster.jpg"
    movie.write_text("fake video", encoding="utf-8")
    poster.write_bytes(b"not really an image")

    metadata = media.describe_media(movie)

    assert metadata["artwork_url"] == f"/media/artwork?path={poster}"

    enriched = media.enrich_record({"path": str(movie), "title": "Movie"})
    assert enriched["media_available"] is True
    assert enriched["artwork_url"] == f"/media/artwork?path={poster}"


@pytest.mark.parametrize(
    (
        "relative_path",
        "expected_title",
        "expected_year",
        "expected_quality",
        "expected_media_type",
        "expected_overview_parts",
        "noise_tokens",
    ),
    [
        (
            "春光乍泄1997/1997-春光乍泄.1997.BD1080p.中文字幕.mp4",
            "春光乍泄",
            1997,
            "1080P",
            "movie",
            ("电影《春光乍泄》", "1997 年", "文件版本 1080P"),
            ("BD1080p", "中文字幕"),
        ),
        (
            "Everything.Everywhere.All.at.Once.2022.1080p.WEB-DL.DDP5.1.Atmos.H.264-FLUX.mkv",
            "Everything Everywhere All at Once",
            2022,
            "1080P",
            "movie",
            ("电影《Everything Everywhere All at Once》", "2022 年", "文件版本 1080P"),
            ("WEB-DL", "DDP", "Atmos", "H.264", "FLUX"),
        ),
        (
            "The.Bear.S01E02.1080p.WEB-DL.x265-GROUP.mkv",
            "The Bear",
            None,
            "1080P",
            "tv",
            ("剧集《The Bear》", "S01E02", "文件版本 1080P"),
            ("S01E02.1080p", "WEB-DL", "x265", "GROUP"),
        ),
        (
            "卧虎藏龙.Crouching.Tiger.Hidden.Dragon.2000.2160p.BluRay.x265.10bit.DTS.国英双语.中英字幕-WiKi.mkv",
            "卧虎藏龙 Crouching Tiger Hidden Dragon",
            2000,
            "2160P",
            "movie",
            ("电影《卧虎藏龙 Crouching Tiger Hidden Dragon》", "2000 年", "文件版本 2160P"),
            ("BluRay", "x265", "DTS", "国英双语", "中英字幕", "WiKi"),
        ),
    ],
)
def test_local_metadata_cleans_titles_from_filename_and_folder_tokens(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    expected_title: str,
    expected_year: int | None,
    expected_quality: str,
    expected_media_type: str,
    expected_overview_parts: tuple[str, ...],
    noise_tokens: tuple[str, ...],
) -> None:
    disable_tmdb(monkeypatch)
    _, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    movie = tmp_path / relative_path
    movie.parent.mkdir(parents=True, exist_ok=True)
    movie.write_text("fake video", encoding="utf-8")

    parsed = media.describe_media(movie)
    metadata = media.metadata.enrich(movie, parsed)

    assert metadata["display_title"] == expected_title
    assert metadata["title"] == expected_title
    assert metadata["year"] == expected_year
    assert metadata["quality"] == expected_quality
    assert metadata["media_type"] == expected_media_type
    for expected in expected_overview_parts:
        assert expected in metadata["overview"]
    for noise in noise_tokens:
        assert noise not in metadata["display_title"]
        assert noise not in metadata["overview"]


def test_scan_sources_indexes_cleaned_local_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disable_tmdb(monkeypatch)
    library, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    movie = tmp_path / "春光乍泄1997" / "1997-春光乍泄.1997.BD1080p.中文字幕.mp4"
    movie.parent.mkdir()
    movie.write_text("fake video", encoding="utf-8")
    source = library.add_source(str(tmp_path))

    media.scan_sources(source_id=source["id"])
    item = library.list_media_items()[0]

    assert item["display_title"] == "春光乍泄"
    assert item["title"] == "春光乍泄"
    assert item["year"] == 1997
    assert "电影《春光乍泄》" in item["overview"]
    assert "BD1080p" not in item["overview"]
    assert "中文字幕" not in item["overview"]


def test_generated_poster_prefers_ffmpeg_frame_when_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_tmdb(monkeypatch)
    _, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    movie = tmp_path / "Frame.Movie.2026.4K.mkv"
    movie.write_text("fake video", encoding="utf-8")

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess:
        assert "scale=600:900:force_original_aspect_ratio=increase,crop=600:900,setsar=1" in command
        Path(command[-1]).write_bytes(b"jpeg frame")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(metadata_module.shutil, "which", lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else None)
    monkeypatch.setattr(metadata_module.subprocess, "run", fake_run)

    metadata = media.metadata.enrich(movie, media.describe_media(movie))

    poster_path = Path(metadata["poster_path"])
    assert poster_path.suffix == ".jpg"
    assert poster_path.read_bytes() == b"jpeg frame"
    assert metadata["artwork_url"] == f"/media/artwork?path={poster_path}"


def test_scan_sources_indexes_media_items(tmp_path: Path) -> None:
    library, media = make_services(tmp_path)
    movie = tmp_path / "Arrival.2016.2160p.mkv"
    episode_dir = tmp_path / "Show"
    episode = episode_dir / "Show.S01E02.1080p.mp4"
    episode_dir.mkdir()
    movie.write_text("fake video", encoding="utf-8")
    episode.write_text("fake video", encoding="utf-8")
    (tmp_path / "Notes.txt").write_text("not media", encoding="utf-8")
    source = library.add_source(str(tmp_path))

    summary = media.scan_sources(source_id=source["id"])
    items = library.list_media_items(sort="title")
    names = {item["name"] for item in items}

    assert summary["sources_scanned"] == 1
    assert summary["items_indexed"] == 2
    assert names == {"Arrival.2016.2160p.mkv", "Show.S01E02.1080p.mp4"}
    assert next(item for item in items if item["name"] == "Arrival.2016.2160p.mkv")["year"] == 2016
    assert next(item for item in items if item["name"] == "Show.S01E02.1080p.mp4")["episode"] == 2
    arrival = next(item for item in items if item["name"] == "Arrival.2016.2160p.mkv")
    assert arrival["overview"]
    assert arrival["metadata_source"] in {"local", "tmdb"}
    assert arrival["artwork_url"].startswith("/media/artwork?path=")


def test_library_facets_count_media_statuses_and_sources(tmp_path: Path) -> None:
    library, _ = make_services(tmp_path)
    source_root = tmp_path / "SourceA"
    offline_root = tmp_path / "SourceB"
    source_root.mkdir()
    offline_root.mkdir()
    source = library.add_source(str(source_root), "Source A")
    offline_source = library.add_source(str(offline_root), "Source B")
    arrival = source_root / "Arrival.2024.1080p.mkv"
    episode = source_root / "Show.S01E02.2025.2160p.mp4"
    archived = offline_root / "Archived.2024.1080p.mkv"
    arrival.write_text("fake video", encoding="utf-8")
    episode.write_text("fake video", encoding="utf-8")
    archived.write_text("fake video", encoding="utf-8")
    seed_indexed_media_item(
        library,
        arrival,
        source,
        title="Arrival",
        year=2024,
        quality="1080P",
        media_type="movie",
    )
    seed_indexed_media_item(
        library,
        episode,
        source,
        title="Show",
        year=2025,
        quality="2160P",
        media_type="tv",
    )
    seed_indexed_media_item(
        library,
        archived,
        offline_source,
        title="Archived",
        year=2024,
        quality="1080P",
        media_type="movie",
        available=0,
    )
    library.set_favorite(str(arrival.resolve()), True, "Arrival")
    library.set_favorite(str(archived.resolve()), True, "Archived")
    archived.unlink()
    offline_root.rmdir()

    facets = library.library_facets()

    assert facets["total"] == 3
    assert facets["available"] == 2
    assert facets["offline"] == 1
    assert facets["favorites"] == 2
    assert facets["media_types"] == [
        {"value": "movie", "label": "Movie", "count": 2},
        {"value": "tv", "label": "TV", "count": 1},
    ]
    assert facets["years"] == [{"value": 2025, "count": 1}, {"value": 2024, "count": 2}]
    assert facets["qualities"] == [
        {"value": "1080P", "count": 2},
        {"value": "2160P", "count": 1},
    ]
    sources = {source["name"]: source for source in facets["sources"]}
    assert sources["Source A"]["count"] == 2
    assert sources["Source A"]["available"] is True
    assert sources["Source B"]["count"] == 1
    assert sources["Source B"]["available"] is False


def test_list_media_items_filters_by_library_facets(tmp_path: Path) -> None:
    library, _ = make_services(tmp_path)
    source_root = tmp_path / "SourceA"
    other_root = tmp_path / "SourceB"
    source_root.mkdir()
    other_root.mkdir()
    source = library.add_source(str(source_root), "Source A")
    other_source = library.add_source(str(other_root), "Source B")
    favorite_movie = source_root / "Arrival.2024.1080p.mkv"
    plain_movie = source_root / "Dune.2024.1080p.mkv"
    episode = other_root / "Show.S01E02.2025.2160p.mp4"
    offline_movie = other_root / "Offline.2024.1080p.mkv"
    for media_path in (favorite_movie, plain_movie, episode, offline_movie):
        media_path.write_text("fake video", encoding="utf-8")
    seed_indexed_media_item(
        library,
        favorite_movie,
        source,
        title="Arrival",
        year=2024,
        quality="1080P",
        media_type="movie",
    )
    seed_indexed_media_item(
        library,
        plain_movie,
        source,
        title="Dune",
        year=2024,
        quality="1080P",
        media_type="movie",
    )
    seed_indexed_media_item(
        library,
        episode,
        other_source,
        title="Show",
        year=2025,
        quality="2160P",
        media_type="tv",
    )
    seed_indexed_media_item(
        library,
        offline_movie,
        other_source,
        title="Offline",
        year=2024,
        quality="1080P",
        media_type="movie",
        available=0,
    )
    library.set_favorite(str(favorite_movie.resolve()), True, "Arrival")
    library.set_favorite(str(offline_movie.resolve()), True, "Offline")

    favorite_results = library.list_media_items(
        media_type="movie",
        year=2024,
        quality="1080P",
        source_id=source["id"],
        favorite=True,
    )
    offline_results = library.list_media_items(available=False, favorite=True)
    non_favorites = library.list_media_items(favorite=False, sort="title")

    assert [item["title"] for item in favorite_results] == ["Arrival"]
    assert [item["title"] for item in offline_results] == ["Offline"]
    assert [item["title"] for item in non_favorites] == ["Dune", "Show"]


def test_scan_sources_skips_disconnected_sources(tmp_path: Path) -> None:
    library, media = make_services(tmp_path)
    disconnected = tmp_path / "MountedNAS"
    disconnected.mkdir()
    library.add_source(str(disconnected))
    disconnected.rmdir()

    summary = media.scan_sources()

    assert summary["sources_scanned"] == 0
    assert summary["sources_skipped"] == 1
    assert summary["items_indexed"] == 0


def test_scan_jobs_store_completion_summary(tmp_path: Path) -> None:
    library, media = make_services(tmp_path)
    movie = tmp_path / "Arrival.2016.2160p.mkv"
    movie.write_text("fake video", encoding="utf-8")
    source = library.add_source(str(tmp_path))

    job = library.create_scan_job(source_id=source["id"], limit=10)
    summary = media.scan_sources(source_id=source["id"], limit=10)
    completed = library.complete_scan_job(job["id"], summary)
    jobs = library.list_scan_jobs()

    assert job["status"] == "running"
    assert completed["status"] == "completed"
    assert completed["source_id"] == source["id"]
    assert completed["limit"] == 10
    assert completed["items_indexed"] == 1
    assert completed["sources_scanned"] == 1
    assert completed["sources_skipped"] == 0
    assert completed["completed_at"] is not None
    assert jobs[0]["id"] == job["id"]


def test_refresh_metadata_rebuilds_single_indexed_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disable_tmdb(monkeypatch)
    library, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    movie = tmp_path / "Better.Title.2024.1080p.mkv"
    movie.write_text("fake video", encoding="utf-8")
    source = library.add_source(str(tmp_path))
    seed_indexed_media_item(library, movie, source, title="Old Local Title")

    summary = media.refresh_metadata(paths=[str(movie)])
    item = indexed_item_by_path(library, movie)

    assert summary["items_refreshed"] == 1
    assert summary["items_missing"] == 0
    assert summary["items_skipped"] == 0
    assert summary["errors"] == []
    assert item["title"] == "Better Title"
    assert item["display_title"] == "Better Title"
    assert item["year"] == 2024
    assert item["quality"] == "1080P"
    assert "电影《Better Title》" in item["overview"]
    assert item["metadata_source"] == "local"
    assert item["artwork_url"].startswith("/media/artwork?path=")


def test_refresh_metadata_filters_by_source_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disable_tmdb(monkeypatch)
    library, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    source_root = tmp_path / "SourceA"
    other_root = tmp_path / "SourceB"
    source_root.mkdir()
    other_root.mkdir()
    source = library.add_source(str(source_root))
    other_source = library.add_source(str(other_root))
    movie = source_root / "Source.Movie.2025.mkv"
    other_movie = other_root / "Other.Movie.2025.mkv"
    movie.write_text("fake video", encoding="utf-8")
    other_movie.write_text("fake video", encoding="utf-8")
    seed_indexed_media_item(library, movie, source, title="Stale Source")
    seed_indexed_media_item(library, other_movie, other_source, title="Stale Other")

    summary = media.refresh_metadata(source_id=source["id"])
    item = indexed_item_by_path(library, movie)
    other_item = indexed_item_by_path(library, other_movie)

    assert summary["items_refreshed"] == 1
    assert summary["items_missing"] == 0
    assert summary["items_skipped"] == 0
    assert item["title"] == "Source Movie"
    assert other_item["title"] == "Stale Other"


def test_refresh_metadata_marks_missing_offline_items_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    disable_tmdb(monkeypatch)
    library, media = make_services(tmp_path)
    source_root = tmp_path / "MountedNAS"
    source_root.mkdir()
    source = library.add_source(str(source_root))
    movie = source_root / "Offline.Movie.2025.mkv"
    movie.write_text("fake video", encoding="utf-8")
    seed_indexed_media_item(library, movie, source, title="Stale Offline")
    movie.unlink()
    source_root.rmdir()

    summary = media.refresh_metadata(source_id=source["id"])
    item = indexed_item_by_path(library, movie)

    assert summary["items_refreshed"] == 0
    assert summary["items_missing"] == 1
    assert summary["items_skipped"] == 1
    assert summary["errors"] == []
    assert item["available"] == 0


def test_refresh_metadata_respects_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disable_tmdb(monkeypatch)
    library, media = make_services(tmp_path)
    media.metadata.poster_dir = tmp_path / "posters"
    source_root = tmp_path / "Limited"
    source_root.mkdir()
    source = library.add_source(str(source_root))
    alpha = source_root / "Alpha.2025.mkv"
    beta = source_root / "Beta.2025.mkv"
    alpha.write_text("fake video", encoding="utf-8")
    beta.write_text("fake video", encoding="utf-8")
    seed_indexed_media_item(library, alpha, source, title="Stale Alpha")
    seed_indexed_media_item(library, beta, source, title="Stale Beta")

    summary = media.refresh_metadata(source_id=source["id"], limit=1)
    alpha_item = indexed_item_by_path(library, alpha)
    beta_item = indexed_item_by_path(library, beta)

    assert summary["items_refreshed"] == 1
    assert summary["items_missing"] == 0
    assert summary["items_skipped"] == 0
    assert summary["limit"] == 1
    assert alpha_item["title"] == "Alpha"
    assert beta_item["title"] == "Stale Beta"


def test_database_initialize_adds_scan_jobs_to_existing_database(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO sources (name, path, created_at) VALUES (?, ?, ?)",
            ("Legacy", str(tmp_path), "2025-01-01T00:00:00+00:00"),
        )

    Database(database_path).initialize()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]

    assert "scan_jobs" in tables
    assert source_count == 1


def test_subtitle_matching_and_encoding_detection(tmp_path: Path) -> None:
    movie = tmp_path / "Arrival.mkv"
    subtitle = tmp_path / "Arrival.en.srt"
    ignored = tmp_path / "Other.en.srt"
    movie.write_text("fake video", encoding="utf-8")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")
    ignored.write_text("ignored", encoding="utf-8")

    tracks = SubtitleManager().match_subtitles(str(movie))

    assert len(tracks) == 1
    assert tracks[0]["path"] == str(subtitle)
    assert tracks[0]["language"] == "English"
    assert tracks[0]["encoding"] in {"utf-8-sig", "utf-8"}


def test_srt_to_webvtt_conversion(tmp_path: Path) -> None:
    subtitle = tmp_path / "Movie.en.srt"
    subtitle.write_text(
        "1\n00:00:01,000 --> 00:00:02,500\nHello\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nWorld\n",
        encoding="utf-8",
    )

    webvtt = SubtitleManager().to_webvtt(str(subtitle))

    assert webvtt.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:02.500" in webvtt
    assert "Hello" in webvtt

    delayed = SubtitleManager().to_webvtt(str(subtitle), offset=1.5)
    assert "00:00:02.500 --> 00:00:04.000" in delayed


def test_ass_to_webvtt_conversion(tmp_path: Path) -> None:
    subtitle = tmp_path / "Movie.zh.ass"
    subtitle.write_text(
        "[Events]\n"
        "Format: Layer, Start, End, Style, Text\n"
        "Dialogue: 0,0:00:01.00,0:00:02.50,Default,{\\i1}你好\\N世界\n",
        encoding="utf-8",
    )

    webvtt = SubtitleManager().to_webvtt(str(subtitle))

    assert "WEBVTT" in webvtt
    assert "00:00:01.000 --> 00:00:02.500" in webvtt
    assert "你好\n世界" in webvtt


def test_mpv_controller_rejects_unplayable_paths_before_launch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    controller = MPVController()
    notes = tmp_path / "notes.txt"
    media = tmp_path / "Playable.mp4"
    notes.write_text("not a video", encoding="utf-8")
    media.write_bytes(b"fake video")

    with pytest.raises(FileNotFoundError, match="Media file does not exist"):
        controller.open(str(tmp_path / "missing.mp4"))
    with pytest.raises(ValueError, match="not a file"):
        controller.open(str(tmp_path))
    with pytest.raises(ValueError, match="supported video file"):
        controller.open(str(notes))

    monkeypatch.setattr("player.mpv_controller.shutil.which", lambda name: None)
    with pytest.raises(MPVUnavailableError, match="mpv is not installed"):
        controller.open(str(media))


def test_mpv_controller_commands_report_no_current_media() -> None:
    controller = MPVController()

    with pytest.raises(OSError, match="No media is currently open"):
        controller.command("pause")
    with pytest.raises(ValueError, match="Unsupported player command"):
        controller.command("dance")

    state = controller.command("stop")
    assert state["running"] is False
