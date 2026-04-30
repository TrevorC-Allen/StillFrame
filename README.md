# StillFrame

StillFrame is a local-first desktop media center for macOS. It uses Electron and React for the library UI, FastAPI for the local backend, SQLite for local state, and `mpv` for high-quality playback in an independent window.

## Current Scope

- Local folders and Finder-mounted NAS paths.
- File browsing with current-folder filter/sort, recent playback, favorites, playback progress, and settings.
- Local library indexing for faster shelves and whole-library views.
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
- `POST /library/scan`
- `POST /history/clear`
- `GET /browse?path=...`
- `POST /play`
- `GET /player/state`
- `POST /player/command`
- `GET /subtitles?media_path=...`
- `POST /favorites`
- `GET /history`
