from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess

from fastapi.testclient import TestClient

from app.main import app
from app import state as app_state
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
    assert "/library/metadata/refresh" in script.text
    assert "refreshMetadata" in script.text
    assert "scheduleScanPoll" in script.text
    assert "Scan running" in script.text
    assert health.status_code == 200
    assert health.json()["ok"] is True
    assert "full_playback_available" in health.json()
    assert "install_hint" in health.json()


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
