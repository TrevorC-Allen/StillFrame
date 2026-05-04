const SERVER_URL = "http://127.0.0.1:8765";

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
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the HTTP status fallback.
    }
    throw new Error(message);
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
  sources: () => request("/sources"),
  addSource: (path, name) => request("/sources", {
    method: "POST",
    body: JSON.stringify({ path, name })
  }),
  library: ({ search = "", sort = "recent", limit = 200, includeUnavailable = true } = {}) => {
    const params = new URLSearchParams({
      limit: String(limit),
      sort
    });
    if (search.trim()) {
      params.set("search", search.trim());
    }
    if (includeUnavailable) {
      params.set("include_unavailable", "true");
    }
    return request(`/library?${params.toString()}`);
  },
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
