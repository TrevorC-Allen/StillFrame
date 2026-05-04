# StillFrame Development Plan

## Product Direction

StillFrame is a local-first media center. The product should feel closer to a focused desktop cinema library than a file manager:

- Open local folders and mounted NAS paths.
- Scan files into a local SQLite library.
- Generate useful posters and descriptions even without network access.
- Optionally enrich metadata through user-provided online metadata credentials.
- Play reliably through mpv while keeping browser preview useful for fast checks.
- Preserve privacy by default: no uploads, no account requirement, no network metadata calls unless configured.

## Near-Term Streams

### Library Operations

- Move scan work into tracked jobs with status, timestamps, summary counts, and errors.
- Support rescanning a single source and all connected sources.
- Add clear stale/unavailable indicators for disconnected drives.
- Keep synchronous scan mode for tests and small libraries.

### Metadata And Details

- Show a full media detail panel in Web MVP.
- Surface poster, overview, source path, metadata source, year, season, episode, quality, and favorite state.
- Add manual refresh later, but keep scan-time enrichment as the first source of truth.

### Desktop Shell

- Bring the Electron React shell up to parity with the Web MVP library index.
- Keep React renderer API-only; no direct SQLite or player access from renderer.
- Defer packaging until the local dev experience is stable.

### Playback

- Prefer mpv for full codec support.
- Keep browser preview for quick play, resume, subtitles, seeking, volume, and fullscreen.
- Add clearer audio codec guidance when browser preview decodes video without audio.

## Validation Gates

Every accepted branch must pass:

- `server/.venv/bin/python -m pytest`
- API smoke checks when server behavior changes.
- Static HTML checks when Web MVP controls are added.
- Manual restart with `./scripts/start_mvp.sh` before pushing integrated main.

## Branch Discipline

- Use one feature branch per worktree.
- Keep worker write scopes disjoint.
- Merge only reviewed, tested work.
- Do not commit local databases, logs, generated poster cache, venvs, or PID files.
