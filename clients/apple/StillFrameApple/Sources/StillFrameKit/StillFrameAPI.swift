import Foundation

public enum StillFrameAPIError: Error, LocalizedError, Sendable {
    case invalidBaseURL(String)
    case invalidURL(String)
    case serverStatus(Int, String)

    public var errorDescription: String? {
        switch self {
        case .invalidBaseURL(let value):
            return "Invalid StillFrame server URL: \(value)"
        case .invalidURL(let endpoint):
            return "Could not build StillFrame API URL for \(endpoint)"
        case .serverStatus(let status, let message):
            return "StillFrame API returned \(status): \(message)"
        }
    }
}

public final class StillFrameAPI: @unchecked Sendable {
    public let baseURL: URL

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(baseURL: URL, session: URLSession = .shared) {
        self.baseURL = baseURL
        self.session = session
        decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
    }

    public convenience init(baseURLString: String) throws {
        guard let url = URL(string: baseURLString), url.scheme != nil, url.host != nil else {
            throw StillFrameAPIError.invalidBaseURL(baseURLString)
        }
        self.init(baseURL: url)
    }

    public func health() async throws -> HealthResponse {
        try await get("/health")
    }

    public func playbackDiagnostics() async throws -> PlaybackDiagnosticsResponse {
        try await get("/diagnostics/playback")
    }

    public func cacheDiagnostics() async throws -> CacheDiagnosticsResponse {
        try await get("/diagnostics/cache")
    }

    public func library(
        search: String? = nil,
        sort: String = "title",
        limit: Int = 100,
        mediaType: String? = nil,
        year: Int? = nil,
        quality: String? = nil,
        sourceId: Int? = nil,
        favorite: Bool? = nil,
        available: Bool? = nil
    ) async throws -> LibraryResponse {
        var query = [
            URLQueryItem(name: "sort", value: sort),
            URLQueryItem(name: "limit", value: String(limit))
        ]
        if let search, !search.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            query.append(URLQueryItem(name: "search", value: search))
        }
        if let mediaType {
            query.append(URLQueryItem(name: "media_type", value: mediaType))
        }
        if let year {
            query.append(URLQueryItem(name: "year", value: String(year)))
        }
        if let quality {
            query.append(URLQueryItem(name: "quality", value: quality))
        }
        if let sourceId {
            query.append(URLQueryItem(name: "source_id", value: String(sourceId)))
        }
        if let favorite {
            query.append(URLQueryItem(name: "favorite", value: favorite ? "true" : "false"))
        }
        if let available {
            query.append(URLQueryItem(name: "available", value: available ? "true" : "false"))
        }
        return try await get("/library", query: query)
    }

    public func facets() async throws -> LibraryFacetsResponse {
        try await get("/library/facets")
    }

    public func browse(path: String) async throws -> BrowseResponse {
        try await get("/browse", query: [URLQueryItem(name: "path", value: path)])
    }

    public func mediaDetails(path: String) async throws -> MediaItem {
        try await get("/media/details", query: [URLQueryItem(name: "path", value: path)])
    }

    public func favorites() async throws -> [MediaItem] {
        try await get("/favorites")
    }

    public func setFavorite(path: String, title: String?, favorite: Bool) async throws -> FavoriteUpdate {
        let body = FavoriteRequest(path: path, title: title, favorite: favorite)
        return try await post("/favorites", body: body)
    }

    @discardableResult
    public func play(path: String, resume: Bool = true, startPosition: Double? = nil) async throws -> PlayerState {
        let body = PlayRequest(path: path, resume: resume, startPosition: startPosition)
        return try await post("/play", body: body)
    }

    public func playerState() async throws -> PlayerState {
        try await get("/player/state")
    }

    @discardableResult
    public func scanLibrary(limit: Int = 5000) async throws -> LibraryScanJob {
        let body = LibraryScanRequest(limit: limit, synchronous: false, wait: false)
        return try await post("/library/scan", body: body)
    }

    @discardableResult
    public func refreshMetadata(limit: Int = 5000, force: Bool = true) async throws -> LibraryMetadataRefreshResponse {
        let body = LibraryMetadataRefreshRequest(limit: limit, force: force)
        return try await post("/library/metadata/refresh", body: body)
    }

    public func streamURL(forPath path: String) throws -> URL {
        try endpointURL("/media/stream", query: [URLQueryItem(name: "path", value: path)])
    }

    public func artworkURL(_ rawValue: String?) -> URL? {
        guard let rawValue, !rawValue.isEmpty else {
            return nil
        }
        if let absolute = URL(string: rawValue), absolute.scheme != nil {
            return absolute
        }
        let artworkPrefix = "/media/artwork?path="
        if rawValue.hasPrefix(artworkPrefix) {
            let path = String(rawValue.dropFirst(artworkPrefix.count))
            return try? endpointURL("/media/artwork", query: [URLQueryItem(name: "path", value: path)])
        }
        if rawValue.hasPrefix("/") {
            return URL(string: normalizedBaseString() + rawValue)
        }
        return try? endpointURL("/media/artwork", query: [URLQueryItem(name: "path", value: rawValue)])
    }

    private func get<Response: Decodable>(
        _ endpoint: String,
        query: [URLQueryItem] = []
    ) async throws -> Response {
        let url = try endpointURL(endpoint, query: query)
        let (data, response) = try await session.data(from: url)
        try validate(response: response, data: data)
        return try decoder.decode(Response.self, from: data)
    }

    private func post<Body: Encodable, Response: Decodable>(
        _ endpoint: String,
        body: Body
    ) async throws -> Response {
        let url = try endpointURL(endpoint)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await session.data(for: request)
        try validate(response: response, data: data)
        return try decoder.decode(Response.self, from: data)
    }

    private func endpointURL(_ endpoint: String, query: [URLQueryItem] = []) throws -> URL {
        var components = URLComponents(string: normalizedBaseString() + endpoint)
        components?.queryItems = query.isEmpty ? nil : query
        guard let url = components?.url else {
            throw StillFrameAPIError.invalidURL(endpoint)
        }
        return url
    }

    private func normalizedBaseString() -> String {
        baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }

    private func validate(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else {
            return
        }
        guard (200..<300).contains(http.statusCode) else {
            let message = String(data: data, encoding: .utf8) ?? HTTPURLResponse.localizedString(forStatusCode: http.statusCode)
            throw StillFrameAPIError.serverStatus(http.statusCode, message)
        }
    }
}

private struct FavoriteRequest: Encodable {
    let path: String
    let title: String?
    let favorite: Bool
}

private struct PlayRequest: Encodable {
    let path: String
    let resume: Bool
    let startPosition: Double?
}

private struct LibraryScanRequest: Encodable {
    let limit: Int
    let synchronous: Bool
    let wait: Bool
}

private struct LibraryMetadataRefreshRequest: Encodable {
    let limit: Int
    let force: Bool
}
