from __future__ import annotations

from pathlib import Path

from app.database import Database
from app.services.library_service import LibraryService
from app.services.media_service import MediaService
from player.subtitle_manager import SubtitleManager


def make_services(tmp_path: Path) -> tuple[LibraryService, MediaService]:
    database = Database(tmp_path / "stillframe-test.db")
    database.initialize()
    library = LibraryService(database)
    return library, MediaService(library)


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
