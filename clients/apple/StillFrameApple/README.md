# StillFrame Apple Clients

This folder contains the native SwiftUI client for macOS, iPadOS, and iOS. It is not a browser wrapper.

## Runtime Shape

- The Mac StillFrame desktop app remains the host for SQLite, local folders, metadata cache, and mpv.
- iPhone and iPad connect to the Mac host over the trusted local network.
- Native preview uses `AVPlayer` through `/media/stream` for formats supported by Apple platforms.
- Full-quality playback can be launched on the Mac host through `POST /play`.

## Run From Xcode

Full iOS/iPadOS app builds require Xcode.

1. Install Xcode and XcodeGen.
2. From this folder, run `xcodegen generate`.
3. Open `StillFrameApple.xcodeproj`.
4. Run the `StillFrame iOS` target on iPhone/iPad, or `StillFrame macOS` for a native SwiftUI Mac client.

The `Package.swift` file is also kept valid so shared code can be checked with:

```bash
swift build --package-path clients/apple/StillFrameApple
```

## Connect iPhone or iPad

The default Electron host binds to `127.0.0.1`, which is correct for private desktop use but invisible to an iPad.
To test on a trusted LAN:

```bash
cd path/to/StillFrame
./scripts/run_server_lan.sh
```

Then enter `http://<mac-lan-ip>:8765` in the native client settings.

This first native client has no account layer and no remote authentication. Use it only on a private network until auth is added.
