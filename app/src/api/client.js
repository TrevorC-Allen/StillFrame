const SERVER_URL = "http://127.0.0.1:8765";
const LEGACY_LIBRARY_SORTS = new Set(["recent", "title", "year", "size"]);

async function request(path, options = {}) {
  const response = await fetch(`${SERVER_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    let body = null;
    try {
      body = await response.json();
      message = formatResponseError(body.detail) || message;
    } catch {
      // Keep the HTTP status fallback.
    }
    const error = new Error(message);
    error.status = response.status;
    error.body = body;
    throw error;
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

export const api = {
  health: () => request("/health"),
  playbackDiagnostics: async () => {
    try {
      const diagnostics = await request("/diagnostics/playback");
      return normalizePlaybackDiagnostics(diagnostics, "diagnostics");
    } catch {
      const health = await request("/health");
      return normalizePlaybackDiagnostics(health, "health");
    }
  },
  cacheDiagnostics: () => request("/diagnostics/cache"),
  clearCache: (bucket = "all") => request(`/diagnostics/cache/clear?bucket=${encodeURIComponent(bucket)}`, {
    method: "POST"
  }),
  sources: () => request("/sources"),
  addSource: (path, name) => request("/sources", {
    method: "POST",
    body: JSON.stringify({ path, name })
  }),
  library: (options = {}) => requestLibrary(options),
  libraryFacets: () => request("/library/facets"),
  scanLibrary: (payload = {}) => request("/library/scan", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  refreshMetadata: (payload = {}) => request("/library/metadata/refresh", {
    method: "POST",
    body: JSON.stringify(payload)
  }),
  scanJobs: ({ limit = 20 } = {}) => {
    const params = new URLSearchParams({
      limit: String(limit)
    });
    return request(`/library/scan/jobs?${params.toString()}`);
  },
  scanJob: (id) => request(`/library/scan/jobs/${encodeURIComponent(id)}`),
  browse: (path) => request(`/browse?path=${encodeURIComponent(path)}`),
  mediaDetails: (path) => request(`/media/details?path=${encodeURIComponent(path)}`),
  play: (path, options = {}) => request("/play", {
    method: "POST",
    body: JSON.stringify({ path, ...options })
  }),
  playerState: () => request("/player/state"),
  playerCommand: (command, value = null) => request("/player/command", {
    method: "POST",
    body: JSON.stringify({ command, value })
  }),
  subtitles: (mediaPath) => request(`/subtitles?media_path=${encodeURIComponent(mediaPath)}`),
  favorites: () => request("/favorites"),
  setFavorite: (path, title, favorite) => request("/favorites", {
    method: "POST",
    body: JSON.stringify({ path, title, favorite })
  }),
  history: () => request("/history"),
  clearHistory: () => request("/history/clear", { method: "POST" }),
  settings: () => request("/settings"),
  setSetting: (key, value) => request("/settings", {
    method: "POST",
    body: JSON.stringify({ key, value })
  })
};

async function requestLibrary(options = {}) {
  const params = libraryParams(options);
  const modernParams = hasModernLibraryParams(params, options.sort || "recent");

  try {
    return await request(`/library?${params.toString()}`);
  } catch (error) {
    if (!modernParams || !shouldRetryLegacyLibrary(error)) {
      throw error;
    }

    try {
      return await request(`/library?${legacyLibraryParams(options).toString()}`);
    } catch {
      throw error;
    }
  }
}

function libraryParams(options = {}) {
  const {
    search = "",
    sort = "recent",
    limit = 200,
    includeUnavailable = true,
    mediaType,
    media_type: mediaTypeSnake,
    year,
    quality,
    sourceId,
    source_id: sourceIdSnake,
    favorite,
    available
  } = options;
  const params = new URLSearchParams({
    limit: String(limit),
    sort
  });
  const trimmedSearch = search.trim();
  if (trimmedSearch) {
    params.set("search", trimmedSearch);
  }
  if (includeUnavailable) {
    params.set("include_unavailable", "true");
  }
  appendFilterParam(params, "media_type", mediaTypeSnake ?? mediaType);
  appendFilterParam(params, "year", year);
  appendFilterParam(params, "quality", quality);
  appendFilterParam(params, "source_id", sourceIdSnake ?? sourceId);
  appendBooleanParam(params, "favorite", favorite);
  appendBooleanParam(params, "available", available);
  return params;
}

function legacyLibraryParams(options = {}) {
  const {
    search = "",
    sort = "recent",
    limit = 200,
    includeUnavailable = true
  } = options;
  const params = new URLSearchParams({
    limit: String(limit),
    sort: LEGACY_LIBRARY_SORTS.has(sort) ? sort : "recent"
  });
  const trimmedSearch = search.trim();
  if (trimmedSearch) {
    params.set("search", trimmedSearch);
  }
  if (includeUnavailable) {
    params.set("include_unavailable", "true");
  }
  return params;
}

function appendFilterParam(params, key, value) {
  if (value == null || value === "" || value === "all") {
    return;
  }
  params.set(key, String(value));
}

function appendBooleanParam(params, key, value) {
  if (value == null || value === "" || value === "all") {
    return;
  }
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (normalized === "true" || normalized === "false") {
      params.set(key, normalized);
    }
    return;
  }
  params.set(key, value ? "true" : "false");
}

function hasModernLibraryParams(params, sort) {
  return (
    !LEGACY_LIBRARY_SORTS.has(sort) ||
    params.has("media_type") ||
    params.has("year") ||
    params.has("quality") ||
    params.has("source_id") ||
    params.has("favorite") ||
    params.has("available")
  );
}

function shouldRetryLegacyLibrary(error) {
  return error?.status === 400 || error?.status === 404 || error?.status === 422;
}

function formatResponseError(detail) {
  if (!detail) {
    return "";
  }
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map(formatResponseError).filter(Boolean).join("; ");
  }
  if (detail.message) {
    return String(detail.message);
  }
  if (detail.msg) {
    return String(detail.msg);
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return String(detail);
  }
}

export function mediaUrl(path) {
  if (!path) {
    return null;
  }
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  return `${SERVER_URL}${path}`;
}

function normalizePlaybackDiagnostics(data = {}, source = "diagnostics") {
  const mpv = normalizeDiagnosticTool(data.mpv, {
    present: data.mpv_present ?? data.mpv_available,
    path: data.mpv_path,
    version: data.mpv_version
  });
  const ffmpeg = normalizeDiagnosticTool(data.ffmpeg, {
    present: data.ffmpeg_present ?? data.ffmpeg_available,
    path: data.ffmpeg_path,
    version: data.ffmpeg_version
  });
  const fullPlaybackAvailable = Boolean(data.full_playback_available ?? (mpv.present && ffmpeg.present));
  const normalized = {
    ...data,
    platform: data.platform || navigator.platform || "Unknown",
    mpv,
    ffmpeg,
    full_playback_available: fullPlaybackAvailable,
    install_hint: data.install_hint || null,
    diagnostics_source: source,
    mpv_available: mpv.present,
    ffmpeg_available: ffmpeg.present,
    mpv_path: mpv.path,
    ffmpeg_path: ffmpeg.path,
    mpv_version: mpv.version,
    ffmpeg_version: ffmpeg.version
  };
  normalized.issues = normalizeDiagnosticIssues(data.issues, normalized);
  return normalized;
}

function normalizeDiagnosticTool(tool, legacy = {}) {
  const raw = tool && typeof tool === "object" ? tool : {};
  const path = raw.path ?? legacy.path ?? (typeof tool === "string" ? tool : null);
  const version = raw.version ?? legacy.version ?? null;
  const presentValue = raw.present ?? raw.available ?? raw.ok ?? legacy.present;
  const present = typeof presentValue === "boolean"
    ? presentValue
    : presentValue == null
      ? Boolean(path || version)
      : Boolean(presentValue);
  return {
    present,
    path: path || null,
    version: version || null
  };
}

function normalizeDiagnosticIssues(issues, diagnostics) {
  const list = Array.isArray(issues) ? issues : issues ? [issues] : [];
  const normalized = list
    .map((issue) => normalizeDiagnosticIssue(issue))
    .filter((issue) => issue.message || issue.action);

  if (!diagnostics.mpv.present) {
    normalized.push({
      code: "missing_mpv",
      severity: "warning",
      message: "mpv is missing.",
      action: diagnostics.install_hint || "Install mpv for native playback."
    });
  }

  if (!diagnostics.ffmpeg.present) {
    normalized.push({
      code: "missing_ffmpeg",
      severity: "warning",
      message: "ffmpeg is missing.",
      action: diagnostics.install_hint || "Install ffmpeg for codec inspection and conversion support."
    });
  }

  return normalized;
}

function normalizeDiagnosticIssue(issue) {
  if (!issue) {
    return { message: "", action: "", severity: "warning", code: "" };
  }
  if (typeof issue === "string") {
    return { message: issue, action: "", severity: "warning", code: "" };
  }
  const action = issue.action ?? issue.fix ?? issue.hint ?? issue.install_hint ?? issue.resolution ?? "";
  const message = issue.message ?? issue.detail ?? issue.description ?? issue.title ?? issue.code ?? "";
  return {
    code: issue.code || "",
    severity: issue.severity || issue.level || "warning",
    message: String(message),
    action: stringifyDiagnosticValue(action)
  };
}

function stringifyDiagnosticValue(value) {
  if (!value) {
    return "";
  }
  if (typeof value === "string") {
    return value;
  }
  if (Array.isArray(value)) {
    return value.map(stringifyDiagnosticValue).filter(Boolean).join("; ");
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}
