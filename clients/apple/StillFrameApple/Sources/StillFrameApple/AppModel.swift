import Foundation
import Combine
import StillFrameKit

@MainActor
final class AppModel: ObservableObject {
    @Published var health: HealthResponse?
    @Published var diagnostics: PlaybackDiagnosticsResponse?
    @Published var cacheDiagnostics: CacheDiagnosticsResponse?
    @Published var facets: LibraryFacetsResponse?
    @Published var sources: [MediaSource] = []
    @Published var browseResponse: BrowseResponse?
    @Published var libraryItems: [MediaItem] = []
    @Published var selectedItem: MediaItem?
    @Published var searchText: String = ""
    @Published var selectedMediaType: String?
    @Published var sort: String = "title"
    @Published var isLoading = false
    @Published var isBrowsing = false
    @Published var isRefreshingMetadata = false
    @Published var isStartingScan = false
    @Published var errorMessage: String?

    private var api: StillFrameAPI?

    func connect(to serverURL: String) async {
        guard let url = URL(string: serverURL), url.scheme != nil, url.host != nil else {
            errorMessage = "Enter a valid StillFrame server URL."
            return
        }

        api = StillFrameAPI(baseURL: url)
        await reloadAll()
    }

    func reloadAll() async {
        guard let api else {
            return
        }

        isLoading = true
        errorMessage = nil
        do {
            async let healthResponse = api.health()
            async let diagnosticsResponse = api.playbackDiagnostics()
            async let cacheResponse = api.cacheDiagnostics()
            async let sourcesResponse = api.sources()
            async let facetsResponse = api.facets()
            async let libraryResponse = api.library(
                search: normalizedSearch,
                sort: sort,
                limit: 200,
                mediaType: selectedMediaType
            )

            health = try await healthResponse
            diagnostics = try await diagnosticsResponse
            cacheDiagnostics = try await cacheResponse
            sources = try await sourcesResponse
            facets = try await facetsResponse
            libraryItems = try await libraryResponse.items
            reconcileSelection()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func reloadLibrary() async {
        guard let api else {
            return
        }

        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.library(
                search: normalizedSearch,
                sort: sort,
                limit: 200,
                mediaType: selectedMediaType
            )
            libraryItems = response.items
            facets = try? await api.facets()
            reconcileSelection()
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func toggleFavorite(_ item: MediaItem) async {
        guard let api else {
            return
        }

        let nextFavorite = !(item.favorite ?? false)
        do {
            let update = try await api.setFavorite(path: item.path, title: item.resolvedTitle, favorite: nextFavorite)
            libraryItems = libraryItems.map { current in
                guard current.path == update.path else {
                    return current
                }
                var copy = current
                copy.favorite = update.favorite
                return copy
            }
            if selectedItem?.path == update.path {
                selectedItem?.favorite = update.favorite
            }
            facets = try? await api.facets()
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func playOnHost(_ item: MediaItem) async {
        guard let api else {
            return
        }

        do {
            _ = try await api.play(path: item.path)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func playOnHost(_ item: BrowseItem) async {
        guard let api else {
            return
        }

        do {
            _ = try await api.play(path: item.path)
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func browse(path: String) async {
        guard let api else {
            return
        }

        isBrowsing = true
        errorMessage = nil
        do {
            browseResponse = try await api.browse(path: path)
        } catch {
            errorMessage = error.localizedDescription
        }
        isBrowsing = false
    }

    func startScan() async {
        guard let api else {
            return
        }

        isStartingScan = true
        errorMessage = nil
        do {
            _ = try await api.scanLibrary()
            await reloadAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        isStartingScan = false
    }

    func refreshMetadata() async {
        guard let api else {
            return
        }

        isRefreshingMetadata = true
        errorMessage = nil
        do {
            _ = try await api.refreshMetadata(limit: 500)
            await reloadAll()
        } catch {
            errorMessage = error.localizedDescription
        }
        isRefreshingMetadata = false
    }

    func previewURL(for item: MediaItem) -> URL? {
        try? api?.streamURL(forPath: item.path)
    }

    func previewURL(for item: BrowseItem) -> URL? {
        item.kind == "video" ? (try? api?.streamURL(forPath: item.path)) : nil
    }

    func artworkURL(for item: MediaItem) -> URL? {
        api?.artworkURL(item.artworkUrl ?? item.posterPath)
    }

    func artworkURL(for item: BrowseItem) -> URL? {
        api?.artworkURL(item.artworkUrl ?? item.posterPath)
    }

    private var normalizedSearch: String? {
        let value = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    private func reconcileSelection() {
        guard let selectedItem else {
            self.selectedItem = libraryItems.first
            return
        }
        self.selectedItem = libraryItems.first { $0.path == selectedItem.path } ?? libraryItems.first
    }
}
