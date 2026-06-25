// swift-tools-version: 5.8
import PackageDescription

let package = Package(
    name: "AriadneClient",
    platforms: [
        .macOS("26.0")
    ],
    products: [
        .executable(name: "AriadneClient", targets: ["AriadneClient"])
    ],
    dependencies: [],
    targets: [
        .executableTarget(
            name: "AriadneClient",
            dependencies: [],
            path: "Sources/AriadneClient"
        )
    ]
)
