import StillFrameKit
import SwiftUI

struct FoldersView: View {
    @ObservedObject var model: AppModel
    @State private var previewItem: BrowseItem?

    var body: some View {
        VStack(spacing: 0) {
            sourceStrip

            if let error = model.errorMessage {
                Label(error, systemImage: "exclamationmark.triangle")
                    .font(.callout)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color.red.opacity(0.14))
            }

            if model.isBrowsing && model.browseResponse == nil {
                ProgressView("Loading folder")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let browse = model.browseResponse {
                List {
                    if let parent = browse.parent {
                        Button {
                            Task { await model.browse(path: parent) }
                        } label: {
                            Label("Back", systemImage: "chevron.left")
                        }
                    }

                    ForEach(browse.items) { item in
                        BrowseRow(
                            item: item,
                            artworkURL: model.artworkURL(for: item),
                            onOpen: {
                                if item.kind == "directory" {
                                    Task { await model.browse(path: item.path) }
                                } else {
                                    previewItem = item
                                }
                            },
                            onPlayHost: {
                                Task { await model.playOnHost(item) }
                            }
                        )
                    }
                }
                .listStyle(.inset)
            } else {
                ContentUnavailableView(
                    "No Folder Selected",
                    systemImage: "folder",
                    description: Text("Choose a source to browse files from the StillFrame host.")
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .navigationTitle(model.browseResponse?.path.split(separator: "/").last.map(String.init) ?? "Folders")
        .toolbar {
            Button {
                Task { await model.reloadAll() }
            } label: {
                Label("Refresh", systemImage: "arrow.clockwise")
            }
        }
        .sheet(item: $previewItem) { item in
            if let url = model.previewURL(for: item) {
                NativePlayerView(title: item.resolvedTitle, url: url)
            }
        }
        .task {
            if model.browseResponse == nil, let source = model.sources.first(where: { $0.available }) {
                await model.browse(path: source.path)
            }
        }
    }

    private var sourceStrip: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(model.sources) { source in
                    Button {
                        Task { await model.browse(path: source.path) }
                    } label: {
                        Label(source.name, systemImage: source.available ? "externaldrive" : "externaldrive.badge.exclamationmark")
                            .lineLimit(1)
                    }
                    .disabled(!source.available)
                    .buttonStyle(.bordered)
                    .help(source.lastError ?? source.path)
                }
            }
            .padding()
        }
        .background(.bar)
    }
}

private struct BrowseRow: View {
    let item: BrowseItem
    let artworkURL: URL?
    let onOpen: () -> Void
    let onPlayHost: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            BrowseArtwork(item: item, url: artworkURL)

            Button(action: onOpen) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(item.resolvedTitle)
                        .font(.headline)
                        .lineLimit(1)
                    metadataLine
                    if let overview = item.overview, !overview.isEmpty {
                        Text(overview)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .buttonStyle(.plain)

            if item.kind == "video" {
                Button(action: onPlayHost) {
                    Image(systemName: "desktopcomputer")
                }
                .buttonStyle(.bordered)
            }
        }
        .padding(.vertical, 4)
    }

    private var metadataLine: some View {
        HStack(spacing: 8) {
            Text(item.kind == "directory" ? "Folder" : "Video")
            if let year = item.year {
                Text(String(year))
            }
            if let quality = item.quality {
                Text(quality)
            }
            if let size = item.size {
                Text(formatBytes(size))
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
    }
}

private struct BrowseArtwork: View {
    let item: BrowseItem
    let url: URL?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(Color.secondary.opacity(0.12))

            if item.kind == "directory" {
                Image(systemName: "folder")
                    .font(.title2)
                    .foregroundStyle(.secondary)
            } else if let url {
                AsyncImage(url: url) { phase in
                    switch phase {
                    case .empty:
                        ProgressView()
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFill()
                    case .failure:
                        Image(systemName: "film")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    @unknown default:
                        EmptyView()
                    }
                }
            } else {
                Image(systemName: "film")
                    .font(.title2)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(width: 48, height: 64)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private func formatBytes(_ size: Int64) -> String {
    let formatter = ByteCountFormatter()
    formatter.allowedUnits = [.useKB, .useMB, .useGB, .useTB]
    formatter.countStyle = .file
    return formatter.string(fromByteCount: size)
}
