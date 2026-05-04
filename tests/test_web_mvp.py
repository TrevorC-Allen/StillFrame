from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from fastapi.testclient import TestClient

from app.main import app
from app import state as app_state
from app.routes import diagnostics as diagnostics_module
from app.services import metadata_service as metadata_module


def test_web_mvp_home_and_health() -> None:
    with TestClient(app) as client:
        home = client.get("/")
        favicon = client.get("/static/favicon.svg")
        mark = client.get("/static/stillframe-mark.svg")
        script = client.get("/static/mvp.js")
        health = client.get("/health")

    assert home.status_code == 200
    assert "StillFrame MVP" in home.text
    assert "stillframe-mark.svg" in home.text
    assert "preview-seek" in home.text
    assert "volume-range" in home.text
    assert "rewind-button" in home.text
    assert "preview-controls" in home.text
    assert "subtitle-select" in home.text
    assert "subtitle-size" in home.text
    assert "subtitle-delay-value" in home.text
    assert "clear-history-button" in home.text
    assert "refresh-sources-button" in home.text
    assert "scan-library-button" in home.text
    assert "scan-status" in home.text
    assert "scan-items-indexed" in home.text
    assert "scan-sources-scanned" in home.text
    assert "scan-sources-skipped" in home.text
    assert "scan-error" in home.text
    assert "metadata-refresh-button" in home.text
    assert "metadata-refresh-status" in home.text
    assert "metadata-items-refreshed" in home.text
    assert "metadata-items-missing" in home.text
    assert "metadata-items-skipped" in home.text
    assert "metadata-refresh-error" in home.text
    assert "library-shelf" in home.text
    assert "library-filter" in home.text
    assert "library-sort" in home.text
    assert "library-facets" in home.text
    assert "library-facet-tabs" in home.text
    assert "library-facet-all" in home.text
    assert "library-facet-movie" in home.text
    assert "library-facet-tv" in home.text
    assert "library-facet-favorites" in home.text
    assert "library-facet-offline" in home.text
    assert "library-year-filter" in home.text
    assert "library-quality-filter" in home.text
    assert "library-source-filter" in home.text
    assert "library-facet-stats" in home.text
    assert "media-detail-drawer" in home.text
    assert "detail-poster" in home.text
    assert "detail-overview" in home.text
    assert "detail-path" in home.text
    assert "detail-metadata-source" in home.text
    assert "detail-play-button" in home.text
    assert "detail-favorite-button" in home.text
    assert "detail-mpv-button" in home.text
    assert "detail-close-button" in home.text
    assert "folder-view-button" in home.text
    assert "library-view-button" in home.text
    assert "browser-filter" in home.text
    assert "browser-sort" in home.text
    assert "forward-button" in home.text
    assert "fullscreen-button" in home.text
    assert "control-mpv-button" in home.text
    assert "health-panel" in home.text
    assert "health-mpv-version" in home.text
    assert "health-ffmpeg-version" in home.text
    assert "health-issues" in home.text
    assert "Fullscreen" in home.text
    assert favicon.status_code == 200
    assert mark.status_code == 200
    assert script.status_code == 200
    assert "/diagnostics/playback" in script.text
    assert "playbackDiagnostics" in script.text
    assert "/library/scan/jobs/" in script.text
    assert "/library/facets" in script.text
    assert "media_type" in script.text
    assert "source_id" in script.text
    assert "available" in script.text
    assert "buildLibraryFacetsFromRows" in script.text
    assert "/library/metadata/refresh" in script.text
    assert "refreshMetadata" in script.text
    assert "scheduleScanPoll" in script.text
    assert "Scan running" in script.text
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert "full_playback_available" in health.json()
    assert "install_hint" in health.json()
    assert health.json()["diagnostics_url"] == "/diagnostics/playback"


def test_playback_diagnostics_reports_missing_tools(monkeypatch) -> None:
    monkeypatch.setattr(app_state.shutil, "which", lambda name: None)

    with TestClient(app) as client:
        diagnostics = client.get("/diagnostics/playback")
        health = client.get("/health")

    payload = diagnostics.json()
    issue_codes = {issue["code"] for issue in payload["issues"]}

    assert diagnostics.status_code == 200
    assert payload["mpv"] == {"present": False, "path": None, "version": None}
    assert payload["ffmpeg"] == {"present": False, "path": None, "version": None}
    assert payload["browser_preview_supported"] is True
    assert payload["full_playback_available"] is False
    assert issue_codes == {"mpv_missing", "ffmpeg_missing"}
    assert payload["install_hint"]
    assert health.status_code == 200
    assert health.json()["mpv_available"] is False
    assert health.json()["ffmpeg_available"] is False
    assert health.json()["full_playback_available"] is False
    assert health.json()["diagnostics_url"] == "/diagnostics/playback"


def test_playback_diagnostics_reads_mocked_tool_versions(monkeypatch) -> None:
    paths = {"mpv": "/opt/homebrew/bin/mpv", "ffmpeg": "/opt/homebrew/bin/ffmpeg"}
    calls = []

    def fake_which(name: str) -> str | None:
        return paths.get(name)

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] <= 1.0
        if command[0] == paths["mpv"]:
            return CompletedProcess(command, 0, stdout="mpv 0.39.0 Copyright\nextra\n", stderr="")
        if command[0] == paths["ffmpeg"]:
            return CompletedProcess(command, 0, stdout="ffmpeg version 7.1.1 Copyright\nextra\n", stderr="")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(app_state.shutil, "which", fake_which)
    monkeypatch.setattr(app_state.subprocess, "run", fake_run)

    with TestClient(app) as client:
        response = client.get("/diagnostics/playback")

    payload = response.json()

    assert response.status_code == 200
    assert payload["mpv"] == {"present": True, "path": paths["mpv"], "version": "mpv 0.39.0 Copyright"}
    assert payload["ffmpeg"] == {
        "present": True,
        "path": paths["ffmpeg"],
        "version": "ffmpeg version 7.1.1 Copyright",
    }
    assert payload["full_playback_available"] is True
    assert payload["issues"] == []
    assert payload["install_hint"] is None
    assert [call[0] for call in calls] == [[paths["mpv"], "--version"], [paths["ffmpeg"], "-version"]]


def test_cache_diagnostics_counts_local_media_cache(tmp_path: Path, monkeypatch) -> None:
    cache_root = tmp_path / "media_cache"
    posters = cache_root / "posters"
    subtitles = cache_root / "subtitles"
    posters.mkdir(parents=True)
    subtitles.mkdir(parents=True)
    (posters / "a.jpg").write_bytes(b"poster-a")
    (posters / "b.svg").write_text("<svg />", encoding="utf-8")
    (subtitles / "movie.srt").write_text("subtitle", encoding="utf-8")
    monkeypatch.setattr(diagnostics_module, "MEDIA_CACHE_DIR", cache_root)

    with TestClient(app) as client:
        response = client.get("/diagnostics/cache")

    payload = response.json()
    buckets = {bucket["name"]: bucket for bucket in payload["buckets"]}

    assert response.status_code == 200
    assert payload["root"] == str(cache_root)
    assert payload["total_files"] == 3
    assert payload["total_bytes"] == len(b"poster-a") + len("<svg />") + len("subtitle")
    assert buckets["posters"]["files"] == 2
    assert buckets["posters"]["extensions"] == {".jpg": 1, ".svg": 1}
    assert buckets["backdrops"]["exists"] is False
    assert buckets["subtitles"]["files"] == 1


def test_web_mvp_source_browse_stream_and_progress(tmp_path: Path) -> None:
    app_state.database.path = tmp_path / "api-test.db"
    app_state.initialize()
    media = tmp_path / "Sample.2025.1080p.mp4"
    poster = tmp_path / "Sample.2025.1080p-poster.jpg"
    subtitle = tmp_path / "Sample.2025.1080p.en.srt"
    media.write_bytes(b"0123456789" * 1024)
    poster.write_bytes(b"poster")
    subtitle.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello\n", encoding="utf-8")

    with TestClient(app) as client:
        source_response = client.post("/sources", json={"path": str(tmp_path)})
        scan_response = client.post(
            "/library/scan",
            json={"source_id": source_response.json()["id"], "synchronous": True},
        )
        library_response = client.get("/library", params={"search": "Sample"})
        browse_response = client.get("/browse", params={"path": str(tmp_path)})
        stream_response = client.get(
            "/media/stream",
            params={"path": str(media)},
            headers={"Range": "bytes=0-99"},
        )
        artwork_response = client.get("/media/artwork", params={"path": str(poster)})
        subtitles_response = client.get("/subtitles", params={"media_path": str(media)})
        webvtt_response = client.get("/subtitles/webvtt", params={"path": str(subtitle)})
        delayed_webvtt_response = client.get(
            "/subtitles/webvtt",
            params={"path": str(subtitle), "offset": 2},
        )
        progress_response = client.post(
            "/history/progress",
            json={
                "path": str(media),
                "title": "Sample",
                "duration": 120,
                "position": 30,
                "paused": True,
                "finished": False,
            },
        )
        favorite_response = client.post(
            "/favorites",
            json={"path": str(media), "title": "Sample", "favorite": True},
        )
        history_response = client.get("/history")
        favorites_response = client.get("/favorites")
        clear_history_response = client.post("/history/clear")
        cleared_history_response = client.get("/history")

    assert source_response.status_code == 200
    assert source_response.json()["available"] is True
    assert scan_response.status_code == 200
    assert scan_response.json()["items_indexed"] == 1
    assert library_response.status_code == 200
    assert library_response.json()["items"][0]["name"] == "Sample.2025.1080p.mp4"
    assert library_response.json()["items"][0]["artwork_url"] == f"/media/artwork?path={poster}"
    assert library_response.json()["items"][0]["overview"]
    assert library_response.json()["items"][0]["metadata_source"] in {"local", "tmdb"}
    assert browse_response.status_code == 200
    sample_item = next(item for item in browse_response.json()["items"] if item["name"] == "Sample.2025.1080p.mp4")
    assert sample_item["display_title"] == "Sample"
    assert sample_item["year"] == 2025
    assert sample_item["quality"] == "1080P"
    assert sample_item["artwork_url"] == f"/media/artwork?path={poster}"
    assert stream_response.status_code == 206
    assert stream_response.headers["content-range"] == "bytes 0-99/10240"
    assert len(stream_response.content) == 100
    assert artwork_response.status_code == 200
    assert subtitles_response.status_code == 200
    assert subtitles_response.json()[0]["path"] == str(subtitle)
    assert webvtt_response.status_code == 200
    assert "WEBVTT" in webvtt_response.text
    assert "00:00:01.000 --> 00:00:02.000" in webvtt_response.text
    assert delayed_webvtt_response.status_code == 200
    assert "00:00:03.000 --> 00:00:04.000" in delayed_webvtt_response.text
    assert progress_response.status_code == 200
    assert progress_response.json()["artwork_url"] == f"/media/artwork?path={poster}"
    assert favorite_response.status_code == 200
    assert history_response.json()[0]["path"] == str(media)
    assert history_response.json()[0]["artwork_url"] == f"/media/artwork?path={poster}"
    assert favorites_response.json()[0]["artwork_url"] == f"/media/artwork?path={poster}"
    assert clear_history_response.status_code == 200
    assert clear_history_response.json()["deleted"] == 1
    assert cleared_history_response.json() == []


def test_library_facets_and_filter_query_endpoint(tmp_path: Path) -> None:
    app_state.database.path = tmp_path / "library-facets.db"
    app_state.initialize()
    source_root = tmp_path / "SourceA"
    offline_root = tmp_path / "SourceB"
    source_root.mkdir()
    offline_root.mkdir()
    source = app_state.library_service.add_source(str(source_root), "Source A")
    offline_source = app_state.library_service.add_source(str(offline_root), "Source B")
    favorite_movie = source_root / "Arrival.2024.1080p.mkv"
    plain_movie = source_root / "Dune.2024.1080p.mkv"
    archived_movie = offline_root / "Archived.2024.1080p.mkv"
    for media_path in (favorite_movie, plain_movie, archived_movie):
        media_path.write_bytes(b"fake video")

    def indexed_item(media_path: Path, source_record: dict, title: str, available: int) -> dict:
        stat = media_path.stat()
        return {
            "path": str(media_path.resolve()),
            "source_id": source_record["id"],
            "source_path": source_record["path"],
            "name": media_path.name,
            "title": title,
            "display_title": title,
            "year": 2024,
            "season": None,
            "episode": None,
            "quality": "1080P",
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "artwork_url": None,
            "overview": "local overview",
            "poster_path": None,
            "backdrop_url": None,
            "tmdb_id": None,
            "media_type": "movie",
            "metadata_source": "local",
            "metadata_updated_at": "2025-01-01T00:00:00+00:00",
            "available": available,
            "last_seen_at": "2025-01-01T00:00:00+00:00",
        }

    app_state.library_service.upsert_media_items(
        [
            indexed_item(favorite_movie, source, "Arrival", 1),
            indexed_item(plain_movie, source, "Dune", 1),
            indexed_item(archived_movie, offline_source, "Archived", 0),
        ]
    )
    app_state.library_service.set_favorite(str(favorite_movie.resolve()), True, "Arrival")
    app_state.library_service.set_favorite(str(archived_movie.resolve()), True, "Archived")
    archived_movie.unlink()
    offline_root.rmdir()

    with TestClient(app) as client:
        facets_response = client.get("/library/facets")
        filtered_response = client.get(
            "/library",
            params={
                "media_type": "movie",
                "year": 2024,
                "quality": "1080P",
                "source_id": source["id"],
                "favorite": True,
            },
        )
        offline_response = client.get("/library", params={"available": False, "favorite": True})

    facets = facets_response.json()
    assert facets_response.status_code == 200
    assert facets["total"] == 3
    assert facets["available"] == 2
    assert facets["offline"] == 1
    assert facets["favorites"] == 2
    assert facets["media_types"] == [{"value": "movie", "label": "Movie", "count": 3}]
    assert facets["years"] == [{"value": 2024, "count": 3}]
    assert facets["qualities"] == [{"value": "1080P", "count": 3}]
    assert {source["name"]: source["count"] for source in facets["sources"]} == {"Source A": 2, "Source B": 1}
    assert next(source for source in facets["sources"] if source["name"] == "Source B")["available"] is False
    assert filtered_response.status_code == 200
    assert [item["title"] for item in filtered_response.json()["items"]] == ["Arrival"]
    assert offline_response.status_code == 200
    assert [item["title"] for item in offline_response.json()["items"]] == ["Archived"]


def test_media_stream_error_responses(tmp_path: Path) -> None:
    media = tmp_path / "Sample.mp4"
    notes = tmp_path / "notes.txt"
    loop = tmp_path / "loop.mp4"
    media.write_bytes(b"0123456789")
    notes.write_text("not a video", encoding="utf-8")
    loop.symlink_to(loop)

    with TestClient(app, raise_server_exceptions=False) as client:
        missing_response = client.get("/media/stream", params={"path": str(tmp_path / "missing.mp4")})
        non_video_response = client.get("/media/stream", params={"path": str(notes)})
        invalid_path_response = client.get("/media/stream", params={"path": str(loop)})
        invalid_range_response = client.get(
            "/media/stream",
            params={"path": str(media)},
            headers={"Range": "bytes=abc-def"},
        )

    assert missing_response.status_code == 404
    assert "Media file does not exist" in missing_response.json()["detail"]
    assert non_video_response.status_code == 400
    assert non_video_response.json()["detail"] == "Path is not a supported video file"
    assert invalid_path_response.status_code == 400
    assert "Invalid media path" in invalid_path_response.json()["detail"]
    assert invalid_range_response.status_code == 416
    assert invalid_range_response.json()["detail"] == "Invalid range header"


def test_play_error_responses(tmp_path: Path, monkeypatch) -> None:
    app_state.database.path = tmp_path / "play-errors.db"
    app_state.initialize()
    app_state.mpv_controller.stop()
    media = tmp_path / "Playable.mp4"
    notes = tmp_path / "notes.txt"
    loop = tmp_path / "loop.mp4"
    media.write_bytes(b"fake video")
    notes.write_text("not a video", encoding="utf-8")
    loop.symlink_to(loop)

    with TestClient(app, raise_server_exceptions=False) as client:
        missing_response = client.post("/play", json={"path": str(tmp_path / "missing.mp4")})
        directory_response = client.post("/play", json={"path": str(tmp_path)})
        non_video_response = client.post("/play", json={"path": str(notes)})
        invalid_path_response = client.post("/play", json={"path": str(loop)})
        monkeypatch.setattr("player.mpv_controller.shutil.which", lambda name: None)
        missing_mpv_response = client.post("/play", json={"path": str(media)})

    assert missing_response.status_code == 404
    assert "Media file does not exist" in missing_response.json()["detail"]
    assert directory_response.status_code == 400
    assert "not a file" in directory_response.json()["detail"]
    assert non_video_response.status_code == 400
    assert "supported video file" in non_video_response.json()["detail"]
    assert invalid_path_response.status_code == 400
    assert "Invalid media path" in invalid_path_response.json()["detail"]
    assert missing_mpv_response.status_code == 503
    assert missing_mpv_response.json()["detail"] == "mpv is not installed or not on PATH"


def test_player_command_error_responses() -> None:
    app_state.mpv_controller.stop()

    with TestClient(app, raise_server_exceptions=False) as client:
        no_media_response = client.post("/player/command", json={"command": "pause"})
        invalid_command_response = client.post("/player/command", json={"command": "dance"})
        invalid_open_response = client.post("/player/command", json={"command": "open", "value": 123})

    assert no_media_response.status_code == 409
    assert no_media_response.json()["detail"] == "No media is currently open"
    assert invalid_command_response.status_code == 400
    assert invalid_command_response.json()["detail"] == "Unsupported player command: dance"
    assert invalid_open_response.status_code == 400
    assert invalid_open_response.json()["detail"] == "open command requires a media path string"


def test_library_scan_job_endpoints(tmp_path: Path) -> None:
    app_state.database.path = tmp_path / "scan-jobs.db"
    app_state.initialize()
    media = tmp_path / "Job.Sample.2026.1080p.mp4"
    media.write_bytes(b"0123456789" * 1024)

    with TestClient(app) as client:
        source_response = client.post("/sources", json={"path": str(tmp_path)})
        job_response = client.post(
            "/library/scan",
            json={"source_id": source_response.json()["id"], "limit": 5},
        )
        job_id = job_response.json()["id"]
        job_status_response = client.get(f"/library/scan/jobs/{job_id}")
        jobs_response = client.get("/library/scan/jobs")
        library_response = client.get("/library", params={"search": "Job Sample"})

    assert source_response.status_code == 200
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "running"
    assert job_response.json()["source_id"] == source_response.json()["id"]
    assert job_response.json()["limit"] == 5
    assert job_status_response.status_code == 200
    assert job_status_response.json()["status"] == "completed"
    assert job_status_response.json()["items_indexed"] == 1
    assert job_status_response.json()["sources_scanned"] == 1
    assert job_status_response.json()["sources_skipped"] == 0
    assert job_status_response.json()["completed_at"] is not None
    assert jobs_response.status_code == 200
    assert jobs_response.json()["items"][0]["id"] == job_id
    assert library_response.status_code == 200
    assert library_response.json()["items"][0]["name"] == "Job.Sample.2026.1080p.mp4"


def test_library_metadata_refresh_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(metadata_module, "TMDB_API_KEY", None)
    monkeypatch.setattr(metadata_module, "TMDB_BEARER_TOKEN", None)
    monkeypatch.setattr(app_state.media_service.metadata, "poster_dir", tmp_path / "posters")
    app_state.database.path = tmp_path / "metadata-refresh.db"
    app_state.initialize()
    media = tmp_path / "Api.Sample.2026.1080p.mp4"
    media.write_bytes(b"0123456789" * 1024)

    with TestClient(app) as client:
        source_response = client.post("/sources", json={"path": str(tmp_path)})
        source = source_response.json()
        stat = media.stat()
        app_state.library_service.upsert_media_items(
            [
                {
                    "path": str(media.resolve()),
                    "source_id": source["id"],
                    "source_path": source["path"],
                    "name": media.name,
                    "title": "Old API Title",
                    "display_title": "Old API Title",
                    "year": None,
                    "season": None,
                    "episode": None,
                    "quality": None,
                    "size": stat.st_size,
                    "modified_at": stat.st_mtime,
                    "artwork_url": None,
                    "overview": "old overview",
                    "poster_path": None,
                    "backdrop_url": None,
                    "tmdb_id": None,
                    "media_type": None,
                    "metadata_source": "stale",
                    "metadata_updated_at": "2025-01-01T00:00:00+00:00",
                    "available": 1,
                    "last_seen_at": "2025-01-01T00:00:00+00:00",
                }
            ]
        )
        refresh_response = client.post(
            "/library/metadata/refresh",
            json={"paths": [str(media)]},
        )
        library_response = client.get("/library", params={"search": "Api Sample"})

    assert source_response.status_code == 200
    assert refresh_response.status_code == 200
    assert refresh_response.json()["items_refreshed"] == 1
    assert refresh_response.json()["items_missing"] == 0
    assert refresh_response.json()["items_skipped"] == 0
    assert refresh_response.json()["errors"] == []
    assert library_response.status_code == 200
    assert library_response.json()["items"][0]["title"] == "Api Sample"
    assert library_response.json()["items"][0]["overview"]
    assert library_response.json()["items"][0]["metadata_source"] == "local"


def test_native_folder_picker_endpoint(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return CompletedProcess(args=args, returncode=0, stdout="/Users/trevorcui/Movies\n", stderr="")

    monkeypatch.setattr("app.routes.dialog.platform.system", lambda: "Darwin")
    monkeypatch.setattr("app.routes.dialog.subprocess.run", fake_run)

    with TestClient(app) as client:
        response = client.post("/dialog/folder")

    assert response.status_code == 200
    assert response.json() == {"path": "/Users/trevorcui/Movies"}
