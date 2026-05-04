# StillFrame

StillFrame is a local-first desktop media center for macOS. It uses Electron and React for the library UI, FastAPI for the local backend, SQLite for local state, and `mpv` for high-quality playback in an independent window.

## Current Scope

- Local folders and Finder-mounted NAS paths.
- File browsing with current-folder filter/sort, recent playback, favorites, playback progress, and settings.
- Local library indexing for faster shelves, full-library search, and whole-library views.
- Poster and overview generation from local filenames, with optional TMDb metadata enrichment.
- Web MVP media details drawer with poster, overview, source path, metadata source, favorite, browser preview, and mpv launch actions.
- Local subtitles matched from the media folder.
- Source availability checks for disconnected NAS paths.
- Browser preview resumes unfinished videos from saved progress.
- No online scraping, online subtitles, cloud sync, media-server login, or default network calls beyond `127.0.0.1`.

## Setup

```bash
cd path/to/StillFrame
./scripts/bootstrap_macos.sh
```

If Homebrew is not installed, install Node.js, mpv, and ffmpeg manually, then run:

```bash
cd path/to/StillFrame/server
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Optional real metadata:

```bash
export STILLFRAME_TMDB_API_KEY="your_tmdb_api_key"
# or
export STILLFRAME_TMDB_BEARER_TOKEN="your_tmdb_read_access_token"
```

Without TMDb credentials, StillFrame stays offline and generates a local poster plus a file-name-based description. With credentials, library scans cache TMDb posters and overviews locally. StillFrame uses the TMDb API but is not endorsed or certified by TMDb.

## Run

Immediate Web MVP:

```bash
cd path/to/StillFrame
./scripts/start_mvp.sh
open http://127.0.0.1:8765
```

Backend only:

```bash
cd path/to/StillFrame
./scripts/run_server.sh
```

Desktop app:

```bash
cd path/to/StillFrame/app
npm install
npm run dev
```

## Web MVP Shortcuts

- Space / K: play or pause
- Left / Right: seek 10 seconds
- Up / Down: volume
- M: mute
- F: fullscreen
- S: cycle subtitles
- `[` / `]`: subtitle delay

## API

The local API listens on `http://127.0.0.1:8765`.

- `GET /health`
- `GET /sources`
- `POST /sources`
- `GET /library`
- `POST /library/scan` starts a background scan job by default.
- `POST /library/scan?synchronous=true` or `POST /library/scan?wait=true` runs a blocking scan and returns the scan summary.
- `GET /library/scan/jobs`
- `GET /library/scan/jobs/{id}`
- `POST /history/clear`
- `GET /browse?path=...`
- `POST /play`
- `GET /player/state`
- `POST /player/command`
- `GET /subtitles?media_path=...`
- `POST /favorites`
- `GET /history`
