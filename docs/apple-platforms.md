# Apple Platform Support

## macOS Desktop Host

StillFrame's primary Mac app is the Electron desktop host. It starts the FastAPI backend, stores packaged app data in the macOS user data directory, and launches mpv for full-quality playback.

Development:

```bash
cd app
npm run dev:macos
```

Packaging:

```bash
./scripts/package_macos.sh
```

The packaged app includes the React UI plus the Python backend and player control layer as Electron extra resources. Runtime SQLite and media cache files are placed under Electron's `userData` directory instead of being written into the app bundle.

App icon assets are generated from `app/assets/icons/stillframe-icon.svg`:

```bash
./scripts/generate_icons.sh
```

The script writes Electron PNG/ICNS assets, updates the web favicon, and rebuilds the native Apple `AppIcon.appiconset` without alpha channels.

## iPadOS and iOS Native Client

The iPad/iPhone client lives in `clients/apple/StillFrameApple`. It is a SwiftUI app, not a browser shell.

It uses:

- `NavigationSplitView` and native SwiftUI controls for system navigation.
- `URLSession` for the StillFrame local API.
- `AsyncImage` for local poster/artwork URLs.
- `AVPlayer` for native preview streams.
- `GET /sources` and `GET /browse` for native folder browsing.
- `GET /media/details` for single-file poster, overview, progress, and favorite state.
- `POST /play` to ask the Mac host to launch mpv for full-quality playback.
- `GET /diagnostics/cache` for media cache status in Diagnostics.

Because iPadOS/iOS cannot run the Electron/Python/mpv host directly, the Mac remains the media server during this stage.

## LAN Testing

The normal desktop host binds the API to `127.0.0.1` for privacy. To connect an iPhone or iPad on a trusted local network:

```bash
./scripts/run_server_lan.sh
```

Then set the native app server URL to `http://<mac-lan-ip>:8765`.

This mode has no authentication yet, so it should stay on a private network.
