// swift-tools-version: 6.0

import PackageDescription

let package = Package(
    name: "StillFrameApple",
    platforms: [
        .iOS(.v17),
        .macOS(.v14)
    ],
    products: [
        .library(name: "StillFrameKit", targets: ["StillFrameKit"]),
        .executable(name: "StillFrameApplePreview", targets: ["StillFrameApple"])
    ],
    targets: [
        .target(name: "StillFrameKit"),
        .executableTarget(
            name: "StillFrameApple",
            dependencies: ["StillFrameKit"]
        )
    ]
)
