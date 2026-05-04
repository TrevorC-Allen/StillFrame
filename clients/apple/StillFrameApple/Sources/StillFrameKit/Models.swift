import Foundation

public struct HealthResponse: Codable, Sendable {
    public let ok: Bool
    public let app: String
    public let version: String
    public let mpvAvailable: Bool
    public let ffmpegAvailable: Bool
    public let mpvPath: String?
    public let ffmpegPath: String?
    public let fullPlaybackAvailable: Bool
    public let installHint: String?
    public let diagnosticsUrl: String?
    public let databasePath: String
}

public struct PlaybackDiagnosticsResponse: Codable, Sendable {
    public let platform: String
    public let pythonVersion: String
    public let mpv: PlaybackToolDiagnostic
    public let ffmpeg: PlaybackToolDiagnostic
    public let browserPreviewSupported: Bool
    public let fullPlaybackAvailable: Bool
    public let issues: [PlaybackDiagnosticIssue]
    public let installHint: String?
}

public struct PlaybackToolDiagnostic: Codable, Sendable {
    public let present: Bool
    public let path: String?
    public let version: String?
}

public struct PlaybackDiagnosticIssue: Codable, Identifiable, Sendable {
    public var id: String { code }

    public let code: String
    public let severity: String
    public let message: String
    public let action: String
}

public struct CacheDiagnosticsResponse: Codable, Sendable {
    public let root: String
    public let totalFiles: Int
    public let totalBytes: Int
    public let buckets: [CacheBucketDiagnostics]
}

public struct CacheBucketDiagnostics: Codable, Identifiable, Sendable {
    public var id: String { name }

    public let name: String
    public let path: String
    public let exists: Bool
    public let files: Int
    public let bytes: Int
    public let extensions: [String: Int]
}

public struct LibraryResponse: Codable, Sendable {
    public let items: [MediaItem]
    public let total: Int
}

public struct BrowseResponse: Codable, Sendable {
    public let path: String
    public let parent: String?
    public let items: [BrowseItem]
}

public struct BrowseItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { path }
    public var resolvedTitle: String { displayTitle ?? title ?? name }

    public let name: String
    public let title: String?
    public let displayTitle: String?
    public let path: String
    public let kind: String
    public let size: Int64?
    public let modifiedAt: Double?
    public let playable: Bool
    public let favorite: Bool
    public let progress: Double?
    public let duration: Double?
    public let position: Double?
    public let year: Int?
    public let season: Int?
    public let episode: Int?
    public let quality: String?
    public let artworkUrl: String?
    public let overview: String?
    public let posterPath: String?
    public let backdropUrl: String?
    public let mediaType: String?
    public let metadataSource: String?
    public let metadataUpdatedAt: String?
}

public struct MediaSource: Codable, Identifiable, Hashable, Sendable {
    public let id: Int
    public let name: String
    public let path: String
    public let createdAt: String
    public let available: Bool
    public let status: String
    public let lastError: String?
}

public struct MediaItem: Codable, Identifiable, Hashable, Sendable {
    public var id: String { path }
    public var resolvedTitle: String { displayTitle ?? title ?? name }

    public let path: String
    public let sourceId: Int?
    public let sourcePath: String?
    public let name: String
    public let title: String?
    public let displayTitle: String?
    public let year: Int?
    public let season: Int?
    public let episode: Int?
    public let quality: String?
    public let size: Int64?
    public let modifiedAt: Double?
    public let artworkUrl: String?
    public let overview: String?
    public let posterPath: String?
    public let backdropUrl: String?
    public let tmdbId: Int?
    public let mediaType: String?
    public let metadataSource: String?
    public let metadataUpdatedAt: String?
    public let available: Bool?
    public let lastSeenAt: String?
    public let duration: Double?
    public let position: Double?
    public let finished: Bool?
    public var favorite: Bool?
}

public struct LibraryFacetsResponse: Codable, Sendable {
    public let total: Int
    public let available: Int
    public let offline: Int
    public let favorites: Int
    public let mediaTypes: [LibraryFacetOption]
    public let years: [LibraryYearFacetOption]
    public let qualities: [LibraryValueFacetOption]
    public let sources: [LibrarySourceFacetOption]
}

public struct LibraryFacetOption: Codable, Identifiable, Hashable, Sendable {
    public var id: String { value }

    public let value: String
    public let label: String?
    public let count: Int
}

public struct LibraryValueFacetOption: Codable, Identifiable, Hashable, Sendable {
    public var id: String { value }

    public let value: String
    public let count: Int
}

public struct LibraryYearFacetOption: Codable, Identifiable, Hashable, Sendable {
    public var id: Int { value }

    public let value: Int
    public let count: Int
}

public struct LibrarySourceFacetOption: Codable, Identifiable, Hashable, Sendable {
    public let id: Int
    public let name: String
    public let path: String
    public let count: Int
    public let available: Bool
}

public struct FavoriteUpdate: Codable, Sendable {
    public let path: String
    public let favorite: Bool
}

public struct PlayerState: Codable, Sendable {
    public let path: String?
    public let title: String?
    public let duration: Double
    public let position: Double
    public let paused: Bool
    public let audioTracks: [TrackInfo]
    public let subtitleTracks: [TrackInfo]
    public let selectedAudio: String?
    public let selectedSubtitle: String?
    public let error: String?
    public let ended: Bool
    public let running: Bool

    enum CodingKeys: String, CodingKey {
        case path
        case title
        case duration
        case position
        case paused
        case audioTracks
        case subtitleTracks
        case selectedAudio
        case selectedSubtitle
        case error
        case ended
        case running
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        path = try container.decodeIfPresent(String.self, forKey: .path)
        title = try container.decodeIfPresent(String.self, forKey: .title)
        duration = try container.decodeIfPresent(Double.self, forKey: .duration) ?? 0
        position = try container.decodeIfPresent(Double.self, forKey: .position) ?? 0
        paused = try container.decodeIfPresent(Bool.self, forKey: .paused) ?? false
        audioTracks = try container.decodeIfPresent([TrackInfo].self, forKey: .audioTracks) ?? []
        subtitleTracks = try container.decodeIfPresent([TrackInfo].self, forKey: .subtitleTracks) ?? []
        selectedAudio = try container.decodeLossyStringIfPresent(forKey: .selectedAudio)
        selectedSubtitle = try container.decodeLossyStringIfPresent(forKey: .selectedSubtitle)
        error = try container.decodeIfPresent(String.self, forKey: .error)
        ended = try container.decodeIfPresent(Bool.self, forKey: .ended) ?? false
        running = try container.decodeIfPresent(Bool.self, forKey: .running) ?? false
    }
}

public struct TrackInfo: Codable, Identifiable, Hashable, Sendable {
    public var id: String { rawId ?? title ?? language ?? codec ?? "track" }

    public let rawId: String?
    public let title: String?
    public let language: String?
    public let codec: String?

    enum CodingKeys: String, CodingKey {
        case rawId = "id"
        case title
        case language = "lang"
        case codec
    }

    public init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        rawId = try container.decodeLossyStringIfPresent(forKey: .rawId)
        title = try container.decodeIfPresent(String.self, forKey: .title)
        language = try container.decodeIfPresent(String.self, forKey: .language)
        codec = try container.decodeIfPresent(String.self, forKey: .codec)
    }
}

public struct LibraryScanJob: Codable, Identifiable, Sendable {
    public let id: Int
    public let status: String
    public let sourceId: Int?
    public let limit: Int
    public let itemsIndexed: Int
    public let sourcesScanned: Int
    public let sourcesSkipped: Int
    public let error: String?
    public let startedAt: String
    public let completedAt: String?
}

public struct LibraryMetadataRefreshResponse: Codable, Sendable {
    public let itemsRefreshed: Int
    public let itemsMissing: Int
    public let itemsSkipped: Int
    public let errors: [LibraryMetadataRefreshError]
    public let limit: Int
}

public struct LibraryMetadataRefreshError: Codable, Identifiable, Sendable {
    public var id: String { "\(path ?? "library")-\(error)" }

    public let path: String?
    public let error: String
}

extension KeyedDecodingContainer {
    func decodeLossyStringIfPresent(forKey key: Key) throws -> String? {
        if let value = try decodeIfPresent(String.self, forKey: key) {
            return value
        }
        if let value = try decodeIfPresent(Int.self, forKey: key) {
            return String(value)
        }
        if let value = try decodeIfPresent(Double.self, forKey: key) {
            return String(value)
        }
        if let value = try decodeIfPresent(Bool.self, forKey: key) {
            return String(value)
        }
        return nil
    }
}
