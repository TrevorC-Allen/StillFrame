const api = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options
    });
    if (!response.ok) {
      let message = `${response.status} ${response.statusText}`;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch {
        // Keep fallback.
      }
      throw new Error(message);
    }
    return response.json();
  },
  playMpv: (path) => api.request("/play", {
    method: "POST",
    body: JSON.stringify({ path })
  }),
  chooseFolder: () => api.request("/dialog/folder", { method: "POST" }),
  health: () => api.request("/health"),
  sources: () => api.request("/sources"),
  addSource: (path) => api.request("/sources", {
    method: "POST",
    body: JSON.stringify({ path })
  }),
  library: (search = "", sort = "recent", limit = 24) => {
    const params = new URLSearchParams({ limit: String(limit), sort });
    if (search) params.set("search", search);
    return api.request(`/library?${params.toString()}`);
  },
  scanLibrary: () => api.request("/library/scan", {
    method: "POST",
    body: JSON.stringify({})
  }),
  browse: (path) => api.request(`/browse?path=${encodeURIComponent(path)}`),
  subtitles: (mediaPath) => api.request(`/subtitles?media_path=${encodeURIComponent(mediaPath)}`),
  history: () => api.request("/history"),
  clearHistory: () => api.request("/history/clear", { method: "POST" }),
  favorites: () => api.request("/favorites"),
  setFavorite: (path, title, favorite) => api.request("/favorites", {
    method: "POST",
    body: JSON.stringify({ path, title, favorite })
  }),
  saveProgress: (payload) => api.request("/history/progress", {
    method: "POST",
    body: JSON.stringify(payload)
  })
};

const state = {
  sources: [],
  libraryItems: [],
  libraryRows: [],
  history: [],
  favoriteItems: [],
  favorites: new Set(),
  subtitles: [],
  browse: null,
  browseError: null,
  mainView: "folders",
  browserFilter: "",
  browserSort: "name",
  libraryFilter: "",
  librarySort: "recent",
  librarySearchTimer: null,
  currentMedia: null,
  resumePosition: 0,
  resumeApplied: false,
  progressTimer: null,
  health: null,
  seeking: false,
  detailItem: null,
  subtitleDelay: 0
};

const PREFS_KEY = "stillframe.mvp.preferences";

const ICONS = {
  drive: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4.5 5.8A2.8 2.8 0 0 1 7.3 3h9.4a2.8 2.8 0 0 1 2.8 2.8v12.4a2.8 2.8 0 0 1-2.8 2.8H7.3a2.8 2.8 0 0 1-2.8-2.8V5.8Z"/><path d="M8 16.5h8"/><path d="M8 7.5h8"/></svg>',
  folder: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3.5 6.5h6l2 2h9v9.2a2.3 2.3 0 0 1-2.3 2.3H5.8a2.3 2.3 0 0 1-2.3-2.3V6.5Z"/><path d="M3.5 6.5v-.7a2.3 2.3 0 0 1 2.3-2.3h3.4l2 2h7a2.3 2.3 0 0 1 2.3 2.3v.7"/></svg>',
  play: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.8c0-1.2 1.3-1.9 2.3-1.3l8.7 5.5c.9.6.9 1.9 0 2.5L10.3 18c-1 .6-2.3-.1-2.3-1.3V5.8Z"/></svg>',
  pause: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14"/><path d="M16 5v14"/></svg>',
  clock: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z"/><path d="M12 7v5l3.4 2"/></svg>',
  star: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8-5.2-2.7-5.2 2.7 1-5.8-4.2-4.1 5.8-.8L12 3.6Z"/></svg>',
  mpv: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="5" width="16" height="11" rx="2.2"/><path d="M9 20h6"/><path d="M12 16v4"/><path d="m11 8 4 2.5-4 2.5V8Z"/></svg>',
  film: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="4" width="14" height="16" rx="2.4"/><path d="M8.5 7.5h2"/><path d="M13.5 7.5h2"/><path d="M8.5 16.5h2"/><path d="M13.5 16.5h2"/><path d="m11 9.5 4 2.5-4 2.5v-5Z"/></svg>',
  volume: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5v5h4l5 4v-13l-5 4H4Z"/><path d="M16 9a4 4 0 0 1 0 6"/></svg>',
  muted: '<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9.5v5h4l5 4v-13l-5 4H4Z"/><path d="m17 9 4 4"/><path d="m21 9-4 4"/></svg>'
};

function icon(name, className = "") {
  return ICONS[name].replace('class="ui-icon"', `class="ui-icon ${className}"`);
}

const els = {
  health: document.querySelector("#health"),
  title: document.querySelector("#title"),
  error: document.querySelector("#error"),
  sourceForm: document.querySelector("#source-form"),
  chooseFolderButton: document.querySelector("#choose-folder-button"),
  scanLibraryButton: document.querySelector("#scan-library-button"),
  sourcePath: document.querySelector("#source-path"),
  refreshSourcesButton: document.querySelector("#refresh-sources-button"),
  sources: document.querySelector("#sources"),
  clearHistoryButton: document.querySelector("#clear-history-button"),
  history: document.querySelector("#history"),
  video: document.querySelector("#video"),
  playerWrap: document.querySelector(".player-wrap"),
  videoStage: document.querySelector(".video-stage"),
  videoEmpty: document.querySelector("#video-empty"),
  rewindButton: document.querySelector("#rewind-button"),
  previewToggle: document.querySelector("#preview-toggle"),
  forwardButton: document.querySelector("#forward-button"),
  previewCurrent: document.querySelector("#preview-current"),
  previewSeek: document.querySelector("#preview-seek"),
  previewDuration: document.querySelector("#preview-duration"),
  muteButton: document.querySelector("#mute-button"),
  volumeRange: document.querySelector("#volume-range"),
  fullscreenButton: document.querySelector("#fullscreen-button"),
  controlMpvButton: document.querySelector("#control-mpv-button"),
  subtitleSelect: document.querySelector("#subtitle-select"),
  subtitleSize: document.querySelector("#subtitle-size"),
  subtitleDelayDown: document.querySelector("#subtitle-delay-down"),
  subtitleDelayUp: document.querySelector("#subtitle-delay-up"),
  subtitleDelayReset: document.querySelector("#subtitle-delay-reset"),
  subtitleDelayValue: document.querySelector("#subtitle-delay-value"),
  subtitleNote: document.querySelector("#subtitle-note"),
  nowPlaying: document.querySelector("#now-playing"),
  playbackNote: document.querySelector("#playback-note"),
  favoriteButton: document.querySelector("#favorite-button"),
  folderViewButton: document.querySelector("#folder-view-button"),
  libraryViewButton: document.querySelector("#library-view-button"),
  backButton: document.querySelector("#back-button"),
  currentPath: document.querySelector("#current-path"),
  browserFilter: document.querySelector("#browser-filter"),
  browserSort: document.querySelector("#browser-sort"),
  items: document.querySelector("#items"),
  libraryShelf: document.querySelector("#library-shelf"),
  libraryItems: document.querySelector("#library-items"),
  libraryCount: document.querySelector("#library-count"),
  libraryFilter: document.querySelector("#library-filter"),
  librarySort: document.querySelector("#library-sort"),
  continueShelf: document.querySelector("#continue-shelf"),
  continueItems: document.querySelector("#continue-items"),
  continueCount: document.querySelector("#continue-count"),
  favoriteShelf: document.querySelector("#favorite-shelf"),
  favoriteItems: document.querySelector("#favorite-items"),
  favoriteCount: document.querySelector("#favorite-count"),
  detailScrim: document.querySelector("#media-detail-scrim"),
  detailDrawer: document.querySelector("#media-detail-drawer"),
  detailCloseButton: document.querySelector("#detail-close-button"),
  detailPoster: document.querySelector("#detail-poster"),
  detailTitle: document.querySelector("#detail-title"),
  detailMeta: document.querySelector("#detail-meta"),
  detailOverview: document.querySelector("#detail-overview"),
  detailPath: document.querySelector("#detail-path"),
  detailMetadataSource: document.querySelector("#detail-metadata-source"),
  detailPlayButton: document.querySelector("#detail-play-button"),
  detailFavoriteButton: document.querySelector("#detail-favorite-button"),
  detailMpvButton: document.querySelector("#detail-mpv-button")
};

boot();

async function boot() {
  loadPreferences();
  bindEvents();
  setFolderSortOptions();
  updatePreviewControls();
  updateSubtitleDelayLabel();
  await refresh();
}

function bindEvents() {
  els.chooseFolderButton.addEventListener("click", async () => {
    await run(async () => {
      const result = await api.chooseFolder();
      if (!result.path) return;
      const source = await api.addSource(result.path);
      await refresh();
      await openFolder(source.path);
    });
  });

  els.sourceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const path = els.sourcePath.value.trim();
    if (!path) return;
    await run(async () => {
      const source = await api.addSource(path);
      els.sourcePath.value = "";
      await refresh();
      await openFolder(source.path);
    });
  });

  els.refreshSourcesButton.addEventListener("click", async () => {
    state.browseError = null;
    await refresh();
  });

  els.scanLibraryButton.addEventListener("click", async () => {
    await scanLibrary();
  });

  els.clearHistoryButton.addEventListener("click", async () => {
    if (state.history.length === 0) return;
    if (!confirm("Clear all recent playback history?")) return;
    await run(async () => {
      await api.clearHistory();
      state.history = [];
      renderHistory();
      renderShelves();
    });
  });

  els.folderViewButton.addEventListener("click", () => setMainView("folders"));
  els.libraryViewButton.addEventListener("click", async () => {
    await setMainView("library");
  });

  els.libraryFilter.addEventListener("input", () => {
    state.libraryFilter = els.libraryFilter.value.trim();
    els.browserFilter.value = state.libraryFilter;
    clearTimeout(state.librarySearchTimer);
    state.librarySearchTimer = setTimeout(() => {
      refreshLibraryOnly()
        .then(() => {
          renderShelves();
          if (state.mainView === "library") renderBrowser();
        })
        .catch((error) => showError(error.message));
    }, 180);
  });

  els.librarySort.addEventListener("change", async () => {
    state.librarySort = els.librarySort.value;
    els.browserSort.value = state.librarySort;
    await run(async () => {
      await refreshLibraryOnly();
      renderShelves();
      if (state.mainView === "library") renderBrowser();
    });
  });

  els.backButton.addEventListener("click", async () => {
    if (state.browse?.parent) {
      await openFolder(state.browse.parent);
    }
  });
  els.browserFilter.addEventListener("input", () => {
    if (state.mainView === "library") {
      state.libraryFilter = els.browserFilter.value.trim();
      els.libraryFilter.value = state.libraryFilter;
      clearTimeout(state.librarySearchTimer);
      state.librarySearchTimer = setTimeout(() => {
        refreshLibraryRows().then(renderBrowser).catch((error) => showError(error.message));
      }, 180);
    } else {
      state.browserFilter = els.browserFilter.value.trim().toLowerCase();
      renderBrowser();
    }
  });
  els.browserSort.addEventListener("change", async () => {
    if (state.mainView === "library") {
      state.librarySort = els.browserSort.value;
      els.librarySort.value = state.librarySort;
      await run(async () => {
        await refreshLibraryRows();
        renderBrowser();
      });
    } else {
      state.browserSort = els.browserSort.value;
      renderBrowser();
    }
  });

  els.favoriteButton.addEventListener("click", async () => {
    if (!state.currentMedia) return;
    await toggleFavorite({
      path: state.currentMedia.path,
      name: state.currentMedia.title
    });
  });
  els.detailCloseButton.addEventListener("click", closeMediaDetail);
  els.detailScrim.addEventListener("click", closeMediaDetail);
  els.detailPlayButton.addEventListener("click", async () => {
    if (!state.detailItem) return;
    await play(state.detailItem);
    closeMediaDetail();
  });
  els.detailFavoriteButton.addEventListener("click", async () => {
    if (!state.detailItem) return;
    await toggleFavorite(state.detailItem);
  });
  els.detailMpvButton.addEventListener("click", async () => {
    if (!state.detailItem) return;
    await openInMpv(state.detailItem);
  });

  els.rewindButton.addEventListener("click", () => skipPreview(-10));
  els.previewToggle.addEventListener("click", togglePreviewPlayback);
  els.forwardButton.addEventListener("click", () => skipPreview(10));
  els.video.addEventListener("click", togglePreviewPlayback);
  els.previewSeek.addEventListener("pointerdown", () => {
    state.seeking = true;
  });
  els.previewSeek.addEventListener("input", () => {
    els.previewCurrent.textContent = formatTime(Number(els.previewSeek.value));
  });
  els.previewSeek.addEventListener("change", () => {
    commitPreviewSeek();
  });
  els.previewSeek.addEventListener("pointerup", () => {
    commitPreviewSeek();
  });
  document.addEventListener("pointerup", () => {
    if (state.seeking) {
      commitPreviewSeek();
    }
  });
  els.volumeRange.addEventListener("input", () => {
    els.video.volume = Number(els.volumeRange.value);
    els.video.muted = els.video.volume === 0;
    savePreferences();
    updatePreviewControls();
  });
  els.muteButton.addEventListener("click", () => {
    els.video.muted = !els.video.muted;
    if (!els.video.muted && els.video.volume === 0) {
      els.video.volume = 1;
      els.volumeRange.value = "1";
    }
    savePreferences();
    updatePreviewControls();
  });
  els.fullscreenButton.addEventListener("click", toggleFullscreen);
  els.controlMpvButton.addEventListener("click", () => {
    if (state.currentMedia) {
      openInMpv(state.currentMedia);
    }
  });
  els.subtitleSelect.addEventListener("change", () => {
    applySubtitle(els.subtitleSelect.value);
  });
  els.subtitleSize.addEventListener("change", () => {
    document.documentElement.style.setProperty("--subtitle-size", els.subtitleSize.value);
    savePreferences();
  });
  els.subtitleDelayDown.addEventListener("click", () => setSubtitleDelay(state.subtitleDelay - 0.5));
  els.subtitleDelayUp.addEventListener("click", () => setSubtitleDelay(state.subtitleDelay + 0.5));
  els.subtitleDelayReset.addEventListener("click", () => setSubtitleDelay(0));

  els.video.addEventListener("loadedmetadata", () => {
    applyResumePosition();
    updatePreviewControls();
    saveProgressSoon();
  });
  els.video.addEventListener("loadeddata", () => {
    els.videoEmpty.classList.add("hidden");
    els.playbackNote.textContent = playbackReadyNote();
    setTimeout(checkLikelyAudioSupport, 1800);
  });
  els.video.addEventListener("error", () => {
    const name = state.currentMedia?.title || "This file";
    els.videoEmpty.classList.remove("hidden");
    els.playbackNote.textContent = `${name} cannot be decoded by the browser preview. Use mpv after installing it for MKV, HEVC, ASS subtitles, and HDR.`;
  });
  els.video.addEventListener("durationchange", updatePreviewControls);
  els.video.addEventListener("timeupdate", updatePreviewControls);
  els.video.addEventListener("volumechange", updatePreviewControls);
  els.video.addEventListener("pause", saveProgressSoon);
  els.video.addEventListener("play", () => {
    ensureAudiblePreview();
    startProgressTimer();
    updatePreviewControls();
  });
  els.video.addEventListener("pause", updatePreviewControls);
  els.video.addEventListener("ended", () => {
    updatePreviewControls();
    saveProgress(true);
  });
  document.addEventListener("fullscreenchange", updatePreviewControls);
  document.addEventListener("webkitfullscreenchange", updatePreviewControls);
  document.addEventListener("keydown", handleKeyboardShortcut);
}

async function refresh() {
  await run(async () => {
    const [health, sources, library, history, favorites] = await Promise.all([
      api.health(),
      api.sources(),
      api.library(),
      api.history(),
      api.favorites()
    ]);
    renderHealth(health);
    state.sources = sources;
    state.libraryItems = library.items || [];
    state.history = history;
    state.favoriteItems = favorites;
    state.favorites = new Set(favorites.map((item) => item.path));
    renderSources();
    renderHistory();
    renderShelves();
    if (!state.browse && !state.browseError && sources.length > 0) {
      const firstAvailable = sources.find((source) => source.available !== false);
      if (firstAvailable) {
        await openFolder(firstAvailable.path);
      } else {
        renderDisconnectedSource(sources[0]);
      }
    }
  });
}

async function scanLibrary() {
  const previousLabel = els.scanLibraryButton.querySelector("span")?.textContent || "Scan Library";
  els.scanLibraryButton.disabled = true;
  const label = els.scanLibraryButton.querySelector("span");
  if (label) label.textContent = "Scanning...";
  await run(async () => {
    const result = await api.scanLibrary();
    await refreshLibraryOnly();
    if (state.mainView === "library") {
      await refreshLibraryRows();
      renderBrowser();
    }
    renderShelves();
    els.playbackNote.textContent = `Indexed ${result.items_indexed} video${result.items_indexed === 1 ? "" : "s"} from ${result.sources_scanned} source${result.sources_scanned === 1 ? "" : "s"}.`;
  });
  if (label) label.textContent = previousLabel;
  els.scanLibraryButton.disabled = false;
}

async function setMainView(view) {
  state.mainView = view;
  els.folderViewButton.classList.toggle("active", view === "folders");
  els.libraryViewButton.classList.toggle("active", view === "library");

  if (view === "library") {
    els.browserFilter.value = state.libraryFilter;
    setLibrarySortOptions();
    els.browserSort.value = state.librarySort;
    await run(async () => {
      await refreshLibraryRows();
      renderBrowser();
    });
    return;
  }

  els.browserFilter.value = state.browserFilter;
  setFolderSortOptions();
  els.browserSort.value = state.browserSort;
  renderBrowser();
}

async function openFolder(path) {
  try {
    hideError();
    state.mainView = "folders";
    els.folderViewButton.classList.add("active");
    els.libraryViewButton.classList.remove("active");
    setFolderSortOptions();
    state.browse = await api.browse(path);
    state.browseError = null;
    state.browserFilter = "";
    els.browserFilter.value = "";
    renderBrowser();
  } catch (error) {
    state.browse = null;
    state.browseError = { path, message: error.message };
    renderBrowser();
    showError(error.message);
  }
}

async function play(item) {
  if (item.media_available === false || item.available === false) {
    showError(`${displayTitle(item)} is offline. Reconnect the source and refresh StillFrame.`);
    return;
  }
  state.currentMedia = {
    ...item,
    path: item.path,
    title: displayTitle(item),
    artwork_url: item.artwork_url
  };
  state.resumePosition = resumePositionFor(item);
  state.resumeApplied = false;
  els.video.src = `/media/stream?path=${encodeURIComponent(item.path)}`;
  els.video.muted = false;
  els.video.volume = Number(els.volumeRange.value) > 0 ? Number(els.volumeRange.value) : 1;
  els.volumeRange.value = String(els.video.volume);
  resetPreviewControls();
  els.video.load();
  els.videoEmpty.classList.add("hidden");
  els.playbackNote.textContent = "Loading browser preview...";
  await els.video.play().catch((error) => {
    els.playbackNote.textContent = error.message || "Browser preview could not start.";
  });
  els.nowPlaying.textContent = state.currentMedia.title;
  els.favoriteButton.disabled = false;
  renderFavoriteButton();
  await loadSubtitles(item.path);
  saveProgressSoon();
}

async function openInMpv(item) {
  if (item.media_available === false || item.available === false) {
    showError(`${displayTitle(item)} is offline. Reconnect the source and refresh StillFrame.`);
    return;
  }
  await run(async () => {
    await api.playMpv(item.path);
    state.currentMedia = {
      ...item,
      path: item.path,
      title: displayTitle(item),
      artwork_url: item.artwork_url
    };
    els.nowPlaying.textContent = state.currentMedia.title;
    els.favoriteButton.disabled = false;
    renderFavoriteButton();
  });
}

async function toggleFavorite(item) {
  const title = displayTitle(item);
  const next = !state.favorites.has(item.path);
  await run(async () => {
    await api.setFavorite(item.path, title, next);
    if (next) state.favorites.add(item.path);
    else state.favorites.delete(item.path);
    renderBrowser();
    renderHistory();
    await refreshLibraryOnly();
    await refreshFavoritesOnly();
    renderShelves();
    renderFavoriteButton();
    renderMediaDetailActions();
  });
}

async function refreshLibraryOnly() {
  const library = await api.library(state.libraryFilter, state.librarySort);
  state.libraryItems = library.items || [];
}

async function refreshLibraryRows() {
  const library = await api.library(state.libraryFilter, state.librarySort, 200);
  state.libraryRows = library.items || [];
}

async function refreshFavoritesOnly() {
  state.favoriteItems = await api.favorites();
  state.favorites = new Set(state.favoriteItems.map((item) => item.path));
}

function renderHealth(health) {
  state.health = health;
  const ready = health.full_playback_available || (health.mpv_available && health.ffmpeg_available);
  const missing = [];
  if (!health.mpv_available) missing.push("mpv");
  if (!health.ffmpeg_available) missing.push("ffmpeg");
  els.health.className = ready ? "health ready" : "health";
  els.health.textContent = ready ? "mpv + ffmpeg ready" : `Missing ${missing.join(" + ")}`;
  els.health.title = ready
    ? `mpv: ${health.mpv_path || "available"}\nffmpeg: ${health.ffmpeg_path || "available"}`
    : health.install_hint || "Install mpv and ffmpeg for full playback.";
  els.controlMpvButton.disabled = !ready || !state.currentMedia;
  renderMediaDetailActions();
}

function renderSources() {
  els.sources.innerHTML = "";
  if (state.sources.length === 0) {
    els.sources.innerHTML = '<div class="sidebar-empty">Choose a local folder or a mounted NAS share to begin.</div>';
    return;
  }

  for (const source of state.sources) {
    const button = document.createElement("button");
    const online = source.available !== false;
    button.className = online ? "side-item" : "side-item offline";
    button.innerHTML = `
      <span class="item-symbol ${online ? "" : "warning"}">${icon("drive")}</span>
      <span class="source-copy">
        <span>${escapeHtml(source.name)}</span>
        <small>${online ? "Available" : escapeHtml(source.last_error || "Unavailable")}</small>
      </span>
    `;
    button.title = online ? source.path : `${source.path}\n${source.last_error || "Unavailable"}`;
    button.addEventListener("click", () => {
      if (online) {
        openFolder(source.path);
      } else {
        renderDisconnectedSource(source);
        showError(`${source.name}: ${source.last_error || "Source unavailable."}`);
      }
    });
    els.sources.append(button);
  }
}

function renderHistory() {
  els.history.innerHTML = "";
  els.clearHistoryButton.disabled = state.history.length === 0;
  if (state.history.length === 0) {
    els.history.innerHTML = '<div class="sidebar-empty">Recent videos will appear here after playback starts.</div>';
    return;
  }

  for (const item of state.history.slice(0, 12)) {
    const button = document.createElement("button");
    const online = item.media_available !== false;
    button.className = online ? "history-item" : "history-item offline";
    button.innerHTML = `
      <span class="item-symbol ${online ? "" : "warning"}">${icon("clock")}</span>
      <span class="source-copy">
        <span>${escapeHtml(item.title)}</span>
        <small>${online ? formatHistoryProgress(item) : "Offline"}</small>
      </span>
    `;
    button.title = item.path;
    button.addEventListener("click", () => play(item));
    els.history.append(button);
  }
}

function renderShelves() {
  const continueItems = state.history
    .filter((item) => item.media_available !== false && item.duration && !item.finished && item.position > 5)
    .slice(0, 10);

  renderPosterShelf(
    els.libraryShelf,
    els.libraryItems,
    els.libraryCount,
    state.libraryItems.filter((item) => item.available !== false).slice(0, 12),
    "Play"
  );
  renderPosterShelf(
    els.continueShelf,
    els.continueItems,
    els.continueCount,
    continueItems,
    "Resume"
  );
  renderPosterShelf(
    els.favoriteShelf,
    els.favoriteItems,
    els.favoriteCount,
    state.favoriteItems.filter((item) => item.media_available !== false).slice(0, 10),
    "Play"
  );
}

function renderPosterShelf(container, target, countTarget, items, actionLabel) {
  container.hidden = items.length === 0;
  countTarget.textContent = items.length ? `${items.length}` : "";
  target.innerHTML = "";

  for (const item of items) {
    const card = document.createElement("div");
    card.className = "poster-card";
    card.title = item.path;

    const art = document.createElement("div");
    art.className = "poster-art";
    if (item.artwork_url) {
      art.style.backgroundImage = `linear-gradient(transparent, rgba(0, 0, 0, 0.45)), url("${item.artwork_url}")`;
      art.textContent = "";
    } else {
      art.classList.add("missing-artwork");
    }

    const detailButton = document.createElement("button");
    detailButton.className = "poster-art-button";
    detailButton.type = "button";
    detailButton.setAttribute("aria-label", `Details for ${displayTitle(item)}`);
    detailButton.addEventListener("click", () => showMediaDetail(item));
    if (!item.artwork_url) {
      detailButton.innerHTML = icon("film", "poster-icon");
    }

    const progress = progressRatio(item);
    if (progress > 0) {
      const progressBar = document.createElement("div");
      progressBar.className = "poster-progress";
      progressBar.innerHTML = `<span style="width: ${Math.round(progress * 100)}%"></span>`;
      art.append(progressBar);
    }

    const playButton = document.createElement("button");
    playButton.className = "poster-play-button";
    playButton.type = "button";
    playButton.disabled = !isMediaAvailable(item);
    playButton.title = isMediaAvailable(item) ? `${actionLabel} ${displayTitle(item)}` : "Media is offline";
    playButton.setAttribute("aria-label", `${actionLabel} ${displayTitle(item)}`);
    playButton.innerHTML = icon("play");
    playButton.addEventListener("click", () => play(item));
    art.append(detailButton, playButton);

    const copyButton = document.createElement("button");
    copyButton.className = "poster-copy";
    copyButton.type = "button";
    copyButton.addEventListener("click", () => showMediaDetail(item));

    const title = document.createElement("span");
    title.className = "poster-title";
    title.textContent = displayTitle(item);

    const subtitle = document.createElement("span");
    subtitle.className = "poster-subtitle";
    subtitle.textContent = `${actionLabel}${progress > 0 ? ` · ${Math.round(progress * 100)}%` : ""}`;

    copyButton.append(title, subtitle);
    card.append(art, copyButton);
    target.append(card);
  }
}

function renderBrowser() {
  if (state.mainView === "library") {
    renderIndexedLibrary();
    return;
  }

  if (state.browseError) {
    els.title.textContent = state.browseError.path.split("/").filter(Boolean).at(-1) || state.browseError.path;
    els.currentPath.textContent = state.browseError.path;
    els.backButton.disabled = true;
    renderEmptyBrowser(
      "Folder unavailable",
      state.browseError.message || "StillFrame cannot read this source right now.",
      "Refresh Sources",
      async () => {
        state.browseError = null;
        await refresh();
      }
    );
    return;
  }

  if (!state.browse) {
    els.title.textContent = "Library";
    els.currentPath.textContent = "No folder selected";
    els.backButton.disabled = true;
    renderEmptyBrowser(
      "No library selected",
      "Pick a local folder or a mounted NAS share. StillFrame will show folders and video files only.",
      "Choose Folder",
      () => els.chooseFolderButton.click()
    );
    return;
  }

  els.title.textContent = state.browse.path.split("/").filter(Boolean).at(-1) || state.browse.path;
  els.currentPath.textContent = state.browse.path;
  els.backButton.disabled = !state.browse.parent;
  els.items.innerHTML = "";

  if (state.browse.items.length === 0) {
    renderEmptyBrowser(
      "No playable videos here",
      "This folder is readable, but it has no subfolders or supported video files in the current MVP.",
      state.browse.parent ? "Back" : "Choose Folder",
      () => state.browse.parent ? openFolder(state.browse.parent) : els.chooseFolderButton.click()
    );
    return;
  }

  const visibleItems = sortedBrowserItems(state.browse.items);
  if (visibleItems.length === 0) {
    renderEmptyBrowser(
      "No matches",
      "Nothing in this folder matches the current filter.",
      "Clear Filter",
      () => {
        state.browserFilter = "";
        els.browserFilter.value = "";
        renderBrowser();
      }
    );
    return;
  }

  for (const item of visibleItems) {
    const row = document.createElement("div");
    row.className = "file-row";

    const main = document.createElement("button");
    main.className = "row-main";
    main.innerHTML = `
      <span class="icon">${item.kind === "directory" ? icon("folder") : icon("film")}</span>
      <span class="row-title">
        <strong>${escapeHtml(displayTitle(item))}</strong>
        <small>${escapeHtml(rowSubtitle(item))}</small>
      </span>
    `;
    main.addEventListener("click", () => {
      if (item.kind === "directory") openFolder(item.path);
      else play(item);
    });

    const progress = document.createElement("span");
    progress.className = "quality-chip";
    progress.textContent = item.kind === "video" ? item.quality || "Video" : "";

    const mpvAction = document.createElement("button");
    mpvAction.className = "icon-action";
    mpvAction.innerHTML = `${icon("mpv")}<span>mpv</span>`;
    mpvAction.disabled = item.kind !== "video" || !state.health?.mpv_available;
    mpvAction.title = state.health?.mpv_available ? "Open in mpv" : "mpv is not installed";
    mpvAction.addEventListener("click", () => openInMpv(item));

    const favoriteAction = document.createElement("button");
    favoriteAction.className = state.favorites.has(item.path) ? "icon-action starred" : "icon-action";
    favoriteAction.innerHTML = `${icon("star")}<span>${state.favorites.has(item.path) ? "Starred" : "Star"}</span>`;
    favoriteAction.disabled = item.kind !== "video";
    favoriteAction.addEventListener("click", () => toggleFavorite(item));

    row.append(main, progress, mpvAction, favoriteAction);
    els.items.append(row);
  }
}

function renderIndexedLibrary() {
  els.title.textContent = "Library";
  els.currentPath.textContent = state.libraryFilter ? `Indexed library matching "${state.libraryFilter}"` : "Indexed library";
  els.backButton.disabled = true;
  els.items.innerHTML = "";

  if (state.libraryRows.length === 0) {
    renderEmptyBrowser(
      state.libraryFilter ? "No library matches" : "Library index is empty",
      state.libraryFilter
        ? "Nothing indexed matches the current search."
        : "Scan your connected sources to build the local library index.",
      state.libraryFilter ? "Clear Search" : "Scan Library",
      async () => {
        if (state.libraryFilter) {
          state.libraryFilter = "";
          els.libraryFilter.value = "";
          els.browserFilter.value = "";
          await refreshLibraryRows();
          renderBrowser();
        } else {
          await scanLibrary();
        }
      }
    );
    return;
  }

  for (const item of state.libraryRows) {
    const online = item.available !== false;
    const row = document.createElement("div");
    row.className = online ? "file-row library-row" : "file-row library-row offline";

    const main = document.createElement("button");
    main.className = "row-main";
    main.title = "Show details";
    main.innerHTML = `
      <span class="icon">${icon("film")}</span>
      <span class="row-title">
        <strong>${escapeHtml(displayTitle(item))}</strong>
        <small>${escapeHtml(librarySubtitle(item))}</small>
        ${item.overview ? `<small class="overview-line">${escapeHtml(item.overview)}</small>` : ""}
      </span>
    `;
    main.addEventListener("click", () => showMediaDetail(item));

    const quality = document.createElement("span");
    quality.className = "quality-chip";
    quality.textContent = online ? item.quality || "Video" : "Offline";

    const playAction = document.createElement("button");
    playAction.className = "icon-action play-action";
    playAction.innerHTML = `${icon("play")}<span>Play</span>`;
    playAction.disabled = !online;
    playAction.title = online ? "Play browser preview" : "Media is offline";
    playAction.addEventListener("click", () => play(item));

    const mpvAction = document.createElement("button");
    mpvAction.className = "icon-action";
    mpvAction.innerHTML = `${icon("mpv")}<span>mpv</span>`;
    mpvAction.disabled = !online || !state.health?.mpv_available;
    mpvAction.title = state.health?.mpv_available ? "Open in mpv" : "mpv is not installed";
    mpvAction.addEventListener("click", () => openInMpv(item));

    const favoriteAction = document.createElement("button");
    favoriteAction.className = state.favorites.has(item.path) || item.favorite ? "icon-action starred" : "icon-action";
    favoriteAction.innerHTML = `${icon("star")}<span>${state.favorites.has(item.path) || item.favorite ? "Starred" : "Star"}</span>`;
    favoriteAction.disabled = !online;
    favoriteAction.addEventListener("click", () => toggleFavorite(item));

    row.append(main, quality, playAction, mpvAction, favoriteAction);
    els.items.append(row);
  }
}

function showMediaDetail(item) {
  if (!item || item.kind === "directory") {
    return;
  }
  state.detailItem = { ...item };
  renderMediaDetail();
  els.detailScrim.hidden = false;
  els.detailDrawer.hidden = false;
  els.detailDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("detail-open");
  window.requestAnimationFrame(() => {
    els.detailCloseButton.focus({ preventScroll: true });
  });
}

function closeMediaDetail() {
  state.detailItem = null;
  els.detailScrim.hidden = true;
  els.detailDrawer.hidden = true;
  els.detailDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("detail-open");
}

function renderMediaDetail() {
  const item = state.detailItem;
  if (!item) {
    return;
  }

  const title = displayTitle(item);
  els.detailTitle.textContent = title;
  els.detailPoster.className = item.artwork_url ? "detail-poster" : "detail-poster missing-artwork";
  els.detailPoster.style.backgroundImage = item.artwork_url
    ? `linear-gradient(transparent, rgba(0, 0, 0, 0.55)), url("${item.artwork_url}")`
    : "";
  els.detailPoster.innerHTML = item.artwork_url ? "" : `${icon("film", "poster-icon")}<span>No artwork</span>`;

  els.detailMeta.innerHTML = "";
  const meta = mediaMetaParts(item);
  for (const label of meta.length ? meta : ["Video file"]) {
    const chip = document.createElement("span");
    chip.className = "detail-chip";
    chip.textContent = label;
    els.detailMeta.append(chip);
  }

  els.detailOverview.textContent = item.overview || "No overview has been generated yet.";
  els.detailPath.textContent = item.path || "";
  els.detailPath.title = item.path || "";
  els.detailMetadataSource.textContent = metadataSourceLabel(item.metadata_source);
  renderMediaDetailActions();
}

function renderMediaDetailActions() {
  if (!els.detailPlayButton || !els.detailFavoriteButton || !els.detailMpvButton) {
    return;
  }

  const item = state.detailItem;
  const online = isMediaAvailable(item);
  els.detailPlayButton.disabled = !online;
  els.detailPlayButton.title = online ? "Play browser preview" : "Media is offline";
  els.detailFavoriteButton.disabled = !online;
  els.detailMpvButton.disabled = !online || !state.health?.mpv_available;
  els.detailMpvButton.title = state.health?.mpv_available ? "Open in mpv" : "mpv is not installed";
  renderDetailFavoriteButton();
}

function renderDetailFavoriteButton() {
  if (!state.detailItem) {
    els.detailFavoriteButton.className = "icon-action detail-action";
    els.detailFavoriteButton.innerHTML = `${icon("star")}<span>Favorite</span>`;
    return;
  }

  const favorite = state.favorites.has(state.detailItem.path);
  els.detailFavoriteButton.className = favorite ? "icon-action detail-action starred" : "icon-action detail-action";
  els.detailFavoriteButton.innerHTML = `${icon("star")}<span>${favorite ? "Starred" : "Favorite"}</span>`;
}

function sortedBrowserItems(items) {
  const query = state.browserFilter;
  const filtered = query
    ? items.filter((item) => {
        const searchable = `${item.name || ""} ${item.display_title || ""} ${item.quality || ""}`.toLowerCase();
        return searchable.includes(query);
      })
    : [...items];

  return filtered.sort((a, b) => {
    const folderOrder = (a.kind === "directory" ? 0 : 1) - (b.kind === "directory" ? 0 : 1);
    if (state.browserSort === "recent") {
      return folderOrder || (b.modified_at || 0) - (a.modified_at || 0) || a.name.localeCompare(b.name);
    }
    if (state.browserSort === "size") {
      return folderOrder || (b.size || 0) - (a.size || 0) || a.name.localeCompare(b.name);
    }
    if (state.browserSort === "type") {
      return a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name);
    }
    return folderOrder || a.name.localeCompare(b.name);
  });
}

function renderDisconnectedSource(source) {
  state.mainView = "folders";
  els.folderViewButton.classList.add("active");
  els.libraryViewButton.classList.remove("active");
  state.browse = null;
  state.browseError = {
    path: source.path,
    message: source.last_error || "Source unavailable."
  };
  renderBrowser();
}

function renderEmptyBrowser(title, message, actionLabel, action) {
  els.items.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty-browser";
  empty.innerHTML = `
    <div>
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(message)}</p>
    </div>
  `;
  if (actionLabel && action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = actionLabel;
    button.addEventListener("click", action);
    empty.querySelector("div").append(button);
  }
  els.items.append(empty);
}

function setFolderSortOptions() {
  setSortOptions([
    ["name", "Name"],
    ["recent", "Recently Modified"],
    ["size", "Size"],
    ["type", "Type"],
  ]);
}

function setLibrarySortOptions() {
  setSortOptions([
    ["recent", "Recent"],
    ["title", "Title"],
    ["year", "Year"],
    ["size", "Size"],
  ]);
}

function setSortOptions(options) {
  els.browserSort.innerHTML = "";
  for (const [value, label] of options) {
    els.browserSort.append(new Option(label, value));
  }
}

function renderFavoriteButton() {
  if (!state.currentMedia) {
    els.favoriteButton.disabled = true;
    els.favoriteButton.innerHTML = `${icon("star")}<span>Favorite</span>`;
    return;
  }
  const favorite = state.favorites.has(state.currentMedia.path);
  els.favoriteButton.innerHTML = `${icon("star")}<span>${favorite ? "Starred" : "Favorite"}</span>`;
  els.favoriteButton.className = favorite ? "icon-action starred" : "icon-action";
}

async function loadSubtitles(mediaPath) {
  clearSubtitleTrack();
  state.subtitles = [];
  els.subtitleSelect.innerHTML = "";
  els.subtitleSelect.append(new Option("Off", ""));
  els.subtitleSelect.disabled = true;
  els.subtitleNote.textContent = "Searching local subtitles...";

  try {
    state.subtitles = await api.subtitles(mediaPath);
  } catch (error) {
    els.subtitleNote.textContent = error.message || "Subtitle lookup failed.";
    return;
  }

  for (const subtitle of state.subtitles) {
    const label = subtitleLabel(subtitle);
    els.subtitleSelect.append(new Option(label, subtitle.path));
  }

  if (state.subtitles.length === 0) {
    els.subtitleNote.textContent = "No local subtitles found.";
    return;
  }

  els.subtitleSelect.disabled = false;
  const preferred = preferredSubtitle(state.subtitles);
  els.subtitleSelect.value = preferred.path;
  applySubtitle(preferred.path);
}

function preferredSubtitle(subtitles) {
  return (
    subtitles.find((subtitle) => ["srt", "vtt"].includes(subtitle.format)) ||
    subtitles[0]
  );
}

function applySubtitle(path) {
  clearSubtitleTrack();
  if (!path) {
    els.subtitleNote.textContent = state.subtitles.length
      ? `${state.subtitles.length} subtitle file${state.subtitles.length > 1 ? "s" : ""} available.`
      : "No local subtitles found.";
    return;
  }

  const subtitle = state.subtitles.find((item) => item.path === path);
  const track = document.createElement("track");
  track.kind = "subtitles";
  track.label = subtitleLabel(subtitle);
  track.srclang = subtitleLanguageCode(subtitle);
  track.src = `/subtitles/webvtt?path=${encodeURIComponent(path)}&offset=${encodeURIComponent(state.subtitleDelay.toFixed(3))}`;
  track.default = true;
  track.dataset.stillframeSubtitle = "true";
  track.addEventListener("load", () => {
    track.track.mode = "showing";
    els.subtitleNote.textContent = `Showing ${track.label}.`;
  });
  track.addEventListener("error", () => {
    els.subtitleNote.textContent = `${track.label} could not be previewed in browser. Try mpv for full subtitle support.`;
  });
  els.video.append(track);

  for (const textTrack of els.video.textTracks) {
    textTrack.mode = textTrack.label === track.label ? "showing" : "disabled";
  }
  els.subtitleNote.textContent = `Loading ${track.label}...`;
}

function setSubtitleDelay(value) {
  state.subtitleDelay = Math.max(Math.min(Math.round(value * 10) / 10, 10), -10);
  updateSubtitleDelayLabel();
  savePreferences();
  if (els.subtitleSelect.value) {
    applySubtitle(els.subtitleSelect.value);
  }
}

function updateSubtitleDelayLabel() {
  els.subtitleDelayValue.textContent = `${state.subtitleDelay.toFixed(1)}s`;
}

function cycleSubtitle() {
  if (!state.currentMedia || state.subtitles.length === 0) {
    return;
  }
  const values = ["", ...state.subtitles.map((subtitle) => subtitle.path)];
  const current = values.indexOf(els.subtitleSelect.value);
  const next = values[(current + 1 + values.length) % values.length];
  els.subtitleSelect.value = next;
  applySubtitle(next);
}

function clearSubtitleTrack() {
  for (const track of [...els.video.querySelectorAll("track[data-stillframe-subtitle='true']")]) {
    track.remove();
  }
  for (const textTrack of els.video.textTracks) {
    textTrack.mode = "disabled";
  }
}

function subtitleLabel(subtitle) {
  if (!subtitle) {
    return "Subtitle";
  }
  const parts = [];
  if (subtitle.language) parts.push(subtitle.language);
  parts.push((subtitle.format || "sub").toUpperCase());
  if (subtitle.encoding) parts.push(subtitle.encoding);
  return parts.join(" · ");
}

function subtitleLanguageCode(subtitle) {
  const language = (subtitle?.language || "").toLowerCase();
  if (language.includes("chinese")) return "zh";
  if (language.includes("english")) return "en";
  if (language.includes("japanese")) return "ja";
  if (language.includes("korean")) return "ko";
  return "und";
}

function displayTitle(item) {
  return item.display_title || item.title || item.name || item.path?.split("/").at(-1) || "Untitled";
}

function mediaMetaParts(item) {
  const parts = [];
  const mediaType = mediaTypeLabel(item.media_type);
  if (mediaType) parts.push(mediaType);
  if (item.year) parts.push(String(item.year));
  const episode = episodeLabel(item);
  if (episode) parts.push(episode);
  if (item.quality) parts.push(String(item.quality));
  return parts;
}

function mediaTypeLabel(value) {
  const normalized = String(value || "").toLowerCase();
  if (normalized === "movie") return "Movie";
  if (normalized === "tv" || normalized === "series" || normalized === "episode") return "TV";
  return "";
}

function episodeLabel(item) {
  if (item.season == null || item.episode == null) {
    return "";
  }
  return `S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`;
}

function metadataSourceLabel(source) {
  const normalized = String(source || "").toLowerCase();
  if (normalized === "tmdb") return "TMDb";
  if (normalized === "local") return "Local filename";
  return "Not indexed";
}

function rowSubtitle(item) {
  if (item.kind === "directory") {
    return item.path;
  }
  const parts = [];
  if (item.year) parts.push(item.year);
  const episode = episodeLabel(item);
  if (episode) parts.push(episode);
  if (item.progress) parts.push(`${Math.round(item.progress * 100)}% watched`);
  return parts.join(" · ") || item.name || "";
}

function librarySubtitle(item) {
  const parts = [];
  if (item.year) parts.push(item.year);
  const episode = episodeLabel(item);
  if (episode) parts.push(episode);
  if (item.position && item.duration) {
    parts.push(`${Math.round((item.position / item.duration) * 100)}% watched`);
  }
  const folder = item.source_path ? item.source_path.split("/").filter(Boolean).at(-1) : "";
  if (folder) parts.push(folder);
  return parts.join(" · ") || item.name || "";
}

function formatHistoryProgress(item) {
  if (!item.duration) {
    return "Ready";
  }
  return `${Math.round(((item.position || 0) / item.duration) * 100)}% watched`;
}

function progressRatio(item) {
  if (item.duration) {
    return Math.min((item.position || 0) / item.duration, 1);
  }
  return item.progress || 0;
}

function isMediaAvailable(item) {
  return Boolean(item) && item.media_available !== false && item.available !== false;
}

function startProgressTimer() {
  clearInterval(state.progressTimer);
  state.progressTimer = setInterval(() => saveProgress(false), 5000);
}

async function togglePreviewPlayback() {
  if (!state.currentMedia) {
    return;
  }
  if (els.video.paused) {
    ensureAudiblePreview();
    await els.video.play().catch((error) => {
      els.playbackNote.textContent = error.message || "Browser preview could not start.";
    });
  } else {
    els.video.pause();
  }
  updatePreviewControls();
}

function skipPreview(seconds) {
  if (!state.currentMedia || !Number.isFinite(els.video.duration)) {
    return;
  }
  const next = Math.min(Math.max((els.video.currentTime || 0) + seconds, 0), els.video.duration);
  els.video.currentTime = next;
  updatePreviewControls();
  saveProgressSoon();
}

function handleKeyboardShortcut(event) {
  const target = event.target;
  if (target && ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName)) {
    return;
  }
  const key = event.key.toLowerCase();
  if (key === "escape" && state.detailItem) {
    event.preventDefault();
    closeMediaDetail();
    return;
  }
  if (state.detailItem && els.detailDrawer.contains(target)) {
    return;
  }
  const handledKeys = [" ", "k", "arrowleft", "arrowright", "arrowup", "arrowdown", "m", "f", "s", "[", "]"];
  if (!handledKeys.includes(key)) {
    return;
  }
  event.preventDefault();

  if (key === " " || key === "k") {
    togglePreviewPlayback();
  } else if (key === "arrowleft") {
    skipPreview(-10);
  } else if (key === "arrowright") {
    skipPreview(10);
  } else if (key === "arrowup") {
    adjustVolume(0.05);
  } else if (key === "arrowdown") {
    adjustVolume(-0.05);
  } else if (key === "m") {
    els.video.muted = !els.video.muted;
    savePreferences();
    updatePreviewControls();
  } else if (key === "f") {
    toggleFullscreen();
  } else if (key === "s") {
    cycleSubtitle();
  } else if (key === "[") {
    setSubtitleDelay(state.subtitleDelay - 0.5);
  } else if (key === "]") {
    setSubtitleDelay(state.subtitleDelay + 0.5);
  }
}

function adjustVolume(delta) {
  const next = Math.max(Math.min((els.video.muted ? 0 : els.video.volume) + delta, 1), 0);
  els.video.volume = next;
  els.video.muted = next === 0;
  els.volumeRange.value = String(next);
  savePreferences();
  updatePreviewControls();
}

function resetPreviewControls() {
  state.seeking = false;
  els.previewSeek.max = "0";
  els.previewSeek.value = "0";
  els.previewCurrent.textContent = "00:00";
  els.previewDuration.textContent = "00:00";
  els.controlMpvButton.disabled = !state.health?.mpv_available;
  updatePreviewControls();
}

function updatePreviewControls() {
  const duration = Number.isFinite(els.video.duration) ? els.video.duration : 0;
  const current = Number.isFinite(els.video.currentTime) ? els.video.currentTime : 0;
  els.previewSeek.max = String(duration || 0);
  els.previewSeek.disabled = !duration;
  if (!state.seeking && document.activeElement !== els.previewSeek) {
    els.previewSeek.value = String(Math.min(current, duration || current));
  }
  els.previewCurrent.textContent = formatTime(current);
  els.previewDuration.textContent = formatTime(duration);
  els.previewToggle.innerHTML = icon(els.video.paused ? "play" : "pause");
  els.previewToggle.setAttribute("aria-label", els.video.paused ? "Play" : "Pause");
  els.rewindButton.disabled = !state.currentMedia || !duration;
  els.previewToggle.disabled = !state.currentMedia;
  els.forwardButton.disabled = !state.currentMedia || !duration;
  els.muteButton.innerHTML = icon(els.video.muted || els.video.volume === 0 ? "muted" : "volume");
  els.muteButton.setAttribute("aria-label", els.video.muted ? "Unmute" : "Mute");
  if (document.activeElement !== els.volumeRange) {
    els.volumeRange.value = String(els.video.muted ? 0 : els.video.volume);
  }
  els.fullscreenButton.disabled = !state.currentMedia;
  els.fullscreenButton.classList.toggle("active", isFullscreenActive());
  els.controlMpvButton.disabled = !state.currentMedia || !state.health?.mpv_available;
}

function commitPreviewSeek() {
  if (!Number.isFinite(els.video.duration)) {
    state.seeking = false;
    return;
  }
  const next = Math.min(Math.max(Number(els.previewSeek.value), 0), els.video.duration);
  els.video.currentTime = next;
  state.seeking = false;
  updatePreviewControls();
  saveProgressSoon();
}

async function toggleFullscreen() {
  if (!state.currentMedia) {
    return;
  }

  try {
    if (isFullscreenActive()) {
      await exitFullscreen();
    } else {
      await enterFullscreen();
    }
  } catch (error) {
    els.playbackNote.textContent = `Fullscreen failed: ${error?.message || "browser blocked the request"}.`;
  } finally {
    updatePreviewControls();
  }
}

async function enterFullscreen() {
  if (els.playerWrap.requestFullscreen) {
    await els.playerWrap.requestFullscreen({ navigationUI: "hide" });
    return;
  }
  if (els.playerWrap.webkitRequestFullscreen) {
    els.playerWrap.webkitRequestFullscreen();
    return;
  }
  if (els.playerWrap.webkitEnterFullscreen) {
    els.playerWrap.webkitEnterFullscreen();
    return;
  }
  if (els.video.webkitEnterFullscreen) {
    els.video.webkitEnterFullscreen();
    return;
  }
  if (els.video.requestFullscreen) {
    await els.video.requestFullscreen({ navigationUI: "hide" });
    return;
  }
  throw new Error("this browser does not expose a fullscreen API");
}

async function exitFullscreen() {
  if (document.exitFullscreen) {
    await document.exitFullscreen();
    return;
  }
  if (document.webkitExitFullscreen) {
    document.webkitExitFullscreen();
    return;
  }
  if (document.webkitCancelFullScreen) {
    document.webkitCancelFullScreen();
  }
}

function isFullscreenActive() {
  return Boolean(
    document.fullscreenElement ||
    document.webkitFullscreenElement ||
    document.webkitCurrentFullScreenElement
  );
}

function ensureAudiblePreview() {
  els.video.muted = false;
  if (!Number.isFinite(els.video.volume) || els.video.volume === 0) {
    els.video.volume = Number(els.volumeRange.value) > 0 ? Number(els.volumeRange.value) : 1;
  }
  els.volumeRange.value = String(els.video.volume);
  savePreferences();
}

function loadPreferences() {
  let preferences = {};
  try {
    preferences = JSON.parse(localStorage.getItem(PREFS_KEY) || "{}");
  } catch {
    preferences = {};
  }

  const volume = Number(preferences.volume);
  if (Number.isFinite(volume)) {
    els.video.volume = Math.max(Math.min(volume, 1), 0);
    els.volumeRange.value = String(els.video.volume);
    els.video.muted = els.video.volume === 0;
  }

  if (preferences.subtitleSize) {
    els.subtitleSize.value = preferences.subtitleSize;
    document.documentElement.style.setProperty("--subtitle-size", preferences.subtitleSize);
  } else {
    document.documentElement.style.setProperty("--subtitle-size", els.subtitleSize.value);
  }

  const subtitleDelay = Number(preferences.subtitleDelay);
  if (Number.isFinite(subtitleDelay)) {
    state.subtitleDelay = Math.max(Math.min(Math.round(subtitleDelay * 10) / 10, 10), -10);
  }
}

function resumePositionFor(item) {
  const duration = Number(item.duration || 0);
  const position = Number(item.position || 0);
  if (duration > 0 && position > 5 && position / duration < 0.95) {
    return position;
  }

  const historyItem = state.history.find((entry) => entry.path === item.path);
  if (!historyItem) {
    return 0;
  }
  const historyDuration = Number(historyItem.duration || 0);
  const historyPosition = Number(historyItem.position || 0);
  if (historyDuration > 0 && historyPosition > 5 && historyPosition / historyDuration < 0.95) {
    return historyPosition;
  }
  return 0;
}

function applyResumePosition() {
  if (state.resumeApplied || !state.resumePosition || !Number.isFinite(els.video.duration)) {
    return;
  }
  const target = Math.min(Math.max(state.resumePosition, 0), Math.max(els.video.duration - 2, 0));
  if (target <= 5) {
    return;
  }
  els.video.currentTime = target;
  state.resumeApplied = true;
}

function savePreferences() {
  const preferences = {
    volume: els.video.muted ? 0 : els.video.volume,
    subtitleSize: els.subtitleSize.value,
    subtitleDelay: state.subtitleDelay,
  };
  localStorage.setItem(PREFS_KEY, JSON.stringify(preferences));
}

function playbackReadyNote() {
  const base = videoLoadedNote();
  if (!state.resumeApplied || !state.resumePosition) {
    return base;
  }
  return `Resumed at ${formatTime(state.resumePosition)} · ${base}`;
}

function videoLoadedNote() {
  const width = els.video.videoWidth;
  const height = els.video.videoHeight;
  const duration = Number.isFinite(els.video.duration) ? ` · ${formatTime(els.video.duration)}` : "";
  if (!width || !height) {
    return `Browser preview loaded${duration}.`;
  }
  return `Browser preview loaded at ${width}x${height}${duration}.`;
}

function checkLikelyAudioSupport() {
  if (!state.currentMedia || els.video.paused || els.video.currentTime < 0.8) {
    return;
  }
  if (els.video.muted || els.video.volume === 0) {
    els.playbackNote.textContent = "Preview audio is muted. Raise the volume slider or unmute.";
    return;
  }
  if ("webkitAudioDecodedByteCount" in els.video && els.video.webkitAudioDecodedByteCount === 0) {
    els.playbackNote.textContent = "Video is playing, but the browser has not decoded audio. This usually means AC3/DTS/TrueHD audio needs mpv.";
  }
}

function saveProgressSoon() {
  setTimeout(() => saveProgress(false), 250);
}

function formatTime(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return "00:00";
  }
  const whole = Math.floor(seconds);
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

async function saveProgress(finished) {
  if (!state.currentMedia || !Number.isFinite(els.video.duration)) return;
  await api.saveProgress({
    path: state.currentMedia.path,
    title: state.currentMedia.title,
    duration: els.video.duration || 0,
    position: els.video.currentTime || 0,
    paused: els.video.paused,
    finished
  }).catch(() => {});
}

async function run(task) {
  try {
    hideError();
    await task();
  } catch (error) {
    showError(error.message);
  }
}

function showError(message) {
  els.error.hidden = false;
  els.error.textContent = message;
}

function hideError() {
  els.error.hidden = true;
  els.error.textContent = "";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
