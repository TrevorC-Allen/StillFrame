# StillFrame Architecture

## Runtime Shape

StillFrame has three local layers:

- Electron main process starts and stops the FastAPI backend, owns the native folder picker, and hosts the desktop window.
- React renderer shows sources, files, history, favorites, player state, and settings. It only talks to FastAPI.
- FastAPI owns SQLite, directory browsing, local subtitle matching, playback history, and mpv JSON IPC.
- Source records include live availability metadata so disconnected mounted paths can be shown without corrupting saved library state.

## Playback

The first version launches mpv as an independent window. The backend starts mpv with:

- `--input-ipc-server` for JSON IPC control.
- `--hwdec=auto-safe` for hardware decoding where possible.
- `--vo=gpu-next` and `--profile=high-quality` for better rendering defaults.
- `--sub-file` for matched local subtitles.

The React UI polls `/player/state` and sends commands through `/player/command`.

## Data

SQLite stores:

- `sources`: local or mounted folders.
- `playback_states`: progress, selected tracks, and recent history.
- `favorites`: favorite files.
- `settings`: simple local preferences.

All data remains local.
