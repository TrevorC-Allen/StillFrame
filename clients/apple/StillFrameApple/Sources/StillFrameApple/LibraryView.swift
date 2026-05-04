import StillFrameKit
import SwiftUI

struct LibraryView: View {
    @ObservedObject var model: AppModel
    @State private var previewItem: MediaItem?

    private let columns = [
        GridItem(.adaptive(minimum: 150, maximum: 220), spacing: 16)
    ]

    var body: some View {
        VStack(spacing: 0) {
            toolbar

            if let error = model.errorMessage {
                ErrorBanner(message: error)
                    .padding(.horizontal)
                    .padding(.bottom, 10)
            }

            if model.isLoading && model.libraryItems.isEmpty {
                ProgressView("Loading library")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if model.libraryItems.isEmpty {
                ContentUnavailableView(
                    "No Indexed Media",
                    systemImage: "film.stack",
                    description: Text("Add sources on the Mac host, then scan the StillFrame library.")
                )
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ScrollView {
                    LazyVGrid(columns: columns, alignment: .leading, spacing: 18) {
                        ForEach(model.libraryItems) { item in
                            MediaCard(
                                item: item,
                                artworkURL: model.artworkURL(for: item),
                                isSelected: model.selectedItem?.path == item.path,
                                onSelect: { model.selectedItem = item },
                                onFavorite: { Task { await model.toggleFavorite(item) } }
                            )
                        }
                    }
                    .padding()
                }
                .overlay(alignment: .trailing) {
                    if let item = model.selectedItem {
                        MediaDetailPanel(
                            item: item,
                            artworkURL: model.artworkURL(for: item),
                            previewAvailable: model.previewURL(for: item) != nil,
                            onPreview: { previewItem = item },
                            onPlayHost: { Task { await model.playOnHost(item) } },
                            onFavorite: { Task { await model.toggleFavorite(item) } }
                        )
                        .frame(width: 330)
                        .padding()
                    }
                }
            }
        }
        .navigationTitle("Library")
        .sheet(item: $previewItem) { item in
            if let url = model.previewURL(for: item) {
                NativePlayerView(title: item.resolvedTitle, url: url)
            }
        }
    }

    private var toolbar: some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                TextField("Search library", text: $model.searchText)
                    .textFieldStyle(.roundedBorder)
                    .onSubmit {
                        Task { await model.reloadLibrary() }
                    }

                Button {
                    Task { await model.reloadLibrary() }
                } label: {
                    Label("Search", systemImage: "magnifyingglass")
                }
                .buttonStyle(.borderedProminent)
            }

            HStack(spacing: 10) {
                Picker("Sort", selection: $model.sort) {
                    Text("Title").tag("title")
                    Text("Recent").tag("recent")
                    Text("Year").tag("year")
                    Text("Size").tag("size")
                }
                .pickerStyle(.segmented)
                .onChange(of: model.sort) { _, _ in
                    Task { await model.reloadLibrary() }
                }

                Picker("Type", selection: mediaTypeBinding) {
                    Text("All").tag("all")
                    ForEach(model.facets?.mediaTypes ?? []) { option in
                        Text(option.label ?? option.value.capitalized).tag(option.value)
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: 150)

                Button {
                    Task { await model.startScan() }
                } label: {
                    Label(model.isStartingScan ? "Scanning" : "Scan", systemImage: "arrow.triangle.2.circlepath")
                }
                .disabled(model.isStartingScan)

                Button {
                    Task { await model.refreshMetadata() }
                } label: {
                    Label(model.isRefreshingMetadata ? "Refreshing" : "Metadata", systemImage: "sparkles")
                }
                .disabled(model.isRefreshingMetadata)
            }
        }
        .padding()
    }

    private var mediaTypeBinding: Binding<String> {
        Binding {
            model.selectedMediaType ?? "all"
        } set: { value in
            model.selectedMediaType = value == "all" ? nil : value
            Task { await model.reloadLibrary() }
        }
    }
}

private struct MediaCard: View {
    let item: MediaItem
    let artworkURL: URL?
    let isSelected: Bool
    let onSelect: () -> Void
    let onFavorite: () -> Void

    var body: some View {
        Button(action: onSelect) {
            VStack(alignment: .leading, spacing: 9) {
                MediaPoster(url: artworkURL)
                    .overlay(alignment: .topTrailing) {
                        Button(action: onFavorite) {
                            Image(systemName: (item.favorite ?? false) ? "heart.fill" : "heart")
                                .symbolRenderingMode(.hierarchical)
                        }
                        .buttonStyle(.bordered)
                        .clipShape(Circle())
                        .padding(8)
                    }

                Text(item.resolvedTitle)
                    .font(.headline)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)

                HStack {
                    if let year = item.year {
                        Text(String(year))
                    }
                    if let quality = item.quality {
                        Text(quality)
                    }
                    if item.available == false {
                        Label("Offline", systemImage: "exclamationmark.triangle")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)

                if let progress = progressValue(item) {
                    ProgressView(value: progress)
                        .tint(.accentColor)
                }
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(isSelected ? Color.accentColor.opacity(0.16) : Color.secondary.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            .contentShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct MediaDetailPanel: View {
    let item: MediaItem
    let artworkURL: URL?
    let previewAvailable: Bool
    let onPreview: () -> Void
    let onPlayHost: () -> Void
    let onFavorite: () -> Void

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                MediaPoster(url: artworkURL)
                    .frame(maxWidth: .infinity)

                Text(item.resolvedTitle)
                    .font(.title2.weight(.semibold))
                    .fixedSize(horizontal: false, vertical: true)

                metadataLine

                if let overview = item.overview, !overview.isEmpty {
                    Text(overview)
                        .font(.body)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }

                if let progress = progressValue(item) {
                    VStack(alignment: .leading, spacing: 6) {
                        ProgressView(value: progress)
                        Text(progressText(item))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                HStack {
                    Button(action: onPreview) {
                        Label("Preview", systemImage: "play.rectangle")
                    }
                    .disabled(!previewAvailable)

                    Button(action: onPlayHost) {
                        Label("Play on Mac", systemImage: "desktopcomputer")
                    }
                    .buttonStyle(.borderedProminent)
                }

                Button(action: onFavorite) {
                    Label((item.favorite ?? false) ? "Remove Favorite" : "Favorite", systemImage: (item.favorite ?? false) ? "heart.slash" : "heart")
                }

                Divider()

                Text(item.path)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .textSelection(.enabled)
            }
            .padding(14)
        }
        .background(.regularMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .shadow(radius: 18, y: 10)
    }

    private var metadataLine: some View {
        HStack(spacing: 8) {
            if let mediaType = item.mediaType {
                Text(mediaType.capitalized)
            }
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

private struct MediaPoster: View {
    let url: URL?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8, style: .continuous)
                .fill(LinearGradient(colors: [.black.opacity(0.86), .accentColor.opacity(0.38)], startPoint: .topLeading, endPoint: .bottomTrailing))

            if let url {
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
                            .font(.system(size: 42))
                            .foregroundStyle(.white.opacity(0.72))
                    @unknown default:
                        EmptyView()
                    }
                }
            } else {
                Image(systemName: "film")
                    .font(.system(size: 42))
                    .foregroundStyle(.white.opacity(0.72))
            }
        }
        .aspectRatio(2.0 / 3.0, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct ErrorBanner: View {
    let message: String

    var body: some View {
        Label(message, systemImage: "exclamationmark.triangle")
            .font(.callout)
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(Color.red.opacity(0.14))
            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private func progressValue(_ item: MediaItem) -> Double? {
    guard let duration = item.duration, duration > 0, let position = item.position else {
        return nil
    }
    return min(max(position / duration, 0), 1)
}

private func progressText(_ item: MediaItem) -> String {
    "\(formatSeconds(item.position ?? 0)) / \(formatSeconds(item.duration ?? 0))"
}

private func formatSeconds(_ seconds: Double) -> String {
    let total = Int(seconds.rounded())
    let hours = total / 3600
    let minutes = (total % 3600) / 60
    let remainingSeconds = total % 60
    if hours > 0 {
        return String(format: "%d:%02d:%02d", hours, minutes, remainingSeconds)
    }
    return String(format: "%d:%02d", minutes, remainingSeconds)
}

private func formatBytes(_ bytes: Int64) -> String {
    let formatter = ByteCountFormatter()
    formatter.allowedUnits = [.useGB, .useMB]
    formatter.countStyle = .file
    return formatter.string(fromByteCount: bytes)
}
