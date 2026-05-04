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
