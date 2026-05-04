import { useCallback, useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { api } from "../api/client.js";
import { FileBrowser } from "../components/FileBrowser.jsx";
import { HistoryList } from "../components/HistoryList.jsx";
import { LibraryPage } from "../pages/LibraryPage.jsx";
import { PlayerPanel } from "../components/PlayerPanel.jsx";
import { SettingsPage } from "../pages/SettingsPage.jsx";
import { Sidebar } from "../components/Sidebar.jsx";

export default function App() {
  const [health, setHealth] = useState(null);
  const [sources, setSources] = useState([]);
  const [libraryItems, setLibraryItems] = useState([]);
  const [browseData, setBrowseData] = useState(null);
  const [browseError, setBrowseError] = useState(null);
  const [history, setHistory] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [settings, setSettings] = useState({});
  const [playerState, setPlayerState] = useState(null);
  const [view, setView] = useState("library");
  const [activePath, setActivePath] = useState(null);
  const [error, setError] = useState(null);
  const [scanJob, setScanJob] = useState(null);
  const [scanStarting, setScanStarting] = useState(false);
  const [metadataRefresh, setMetadataRefresh] = useState(null);
  const [metadataRefreshing, setMetadataRefreshing] = useState(false);
  const [diagnosticsRefreshing, setDiagnosticsRefreshing] = useState(false);

  const favoritePaths = useMemo(
    () => new Set(favorites.map((favorite) => favorite.path)),
    [favorites]
  );
  const scanning = scanStarting || scanJob?.status === "running";

  useEffect(() => {
    refreshAll();
    const unsubscribe = window.stillframe?.onAddFolder?.(() => addFolder());
    return () => unsubscribe?.();
  }, []);

  useEffect(() => {
    const timer = setInterval(async () => {
      try {
        const state = await api.playerState();
        setPlayerState(state);
      } catch {
        // The backend may still be starting. The health check handles visibility.
      }
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!scanJob?.id || scanJob.status !== "running") {
      return undefined;
    }

    let cancelled = false;
    let timeoutId = null;

    async function pollScanJob() {
      try {
        const latest = await api.scanJob(scanJob.id);
        if (cancelled) {
          return;
        }

        if (isFinalScanStatus(latest.status)) {
          const [sourceData, mediaData] = await Promise.all([
            api.sources(),
            loadMediaCollections()
          ]);
          if (cancelled) {
            return;
          }
          setSources(sourceData);
          setLibraryItems(mediaData.libraryItems);
          setHistory(mediaData.history);
          setFavorites(mediaData.favorites);
          setScanJob(latest);
          return;
        }

        setScanJob(latest);
      } catch (caught) {
        if (!cancelled) {
          setError(caught.message);
        }
      }

      if (!cancelled) {
        timeoutId = window.setTimeout(pollScanJob, 1500);
      }
    }

    timeoutId = window.setTimeout(pollScanJob, 900);
    return () => {
      cancelled = true;
      if (timeoutId) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [scanJob?.id, scanJob?.status]);

  async function refreshAll() {
    try {
      const [healthData, sourceData, libraryData, historyData, favoriteData, settingData, scanJobsData] = await Promise.all([
        api.playbackDiagnostics(),
        api.sources(),
        api.library(),
        api.history(),
        api.favorites(),
        api.settings(),
        api.scanJobs({ limit: 1 })
      ]);
      setHealth(healthData);
      setSources(sourceData);
      setLibraryItems(libraryData.items || []);
      setHistory(historyData);
      setFavorites(favoriteData);
      setSettings(settingData);
      setScanJob(scanJobsData.items?.[0] || null);
      if (!browseData && !browseError && sourceData.length > 0) {
        const firstAvailable = sourceData.find((source) => source.available !== false);
        if (firstAvailable) {
          openPath(firstAvailable.path);
        } else {
          setBrowseError({
            path: sourceData[0].path,
            message: sourceData[0].last_error || "Source unavailable."
          });
        }
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  const refreshMediaCollections = useCallback(async () => {
    const mediaData = await loadMediaCollections();
    setLibraryItems(mediaData.libraryItems);
    setHistory(mediaData.history);
    setFavorites(mediaData.favorites);
  }, []);

  async function addFolder() {
    setError(null);
    const selected = await window.stillframe?.chooseFolder?.();
    if (!selected) {
      return;
    }
    try {
      const source = await api.addSource(selected);
      const nextSources = await api.sources();
      setSources(nextSources);
      setView("library");
      await openPath(source.path);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function openPath(path) {
    setError(null);
    try {
      const data = await api.browse(path);
      setBrowseData(data);
      setBrowseError(null);
      setActivePath(data.path);
      setView("library");
    } catch (caught) {
      setBrowseData(null);
      setBrowseError({ path, message: caught.message });
      setError(caught.message);
    }
  }

  function openSource(source) {
    if (source.available === false) {
      setBrowseData(null);
      setBrowseError({ path: source.path, message: source.last_error || "Source unavailable." });
      setActivePath(source.path);
      setView("library");
      setError(`${source.name}: ${source.last_error || "Source unavailable."}`);
      return;
    }
    openPath(source.path);
  }

  async function play(pathOrItem) {
    const path = typeof pathOrItem === "string" ? pathOrItem : pathOrItem.path;
    if (typeof pathOrItem !== "string" && (pathOrItem.media_available === false || pathOrItem.available === false)) {
      setError(`${pathOrItem.title || pathOrItem.path}: source is offline.`);
      return;
    }
    setError(null);
    try {
      const state = await api.play(path);
      setPlayerState(state);
      await refreshMediaCollections();
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function sendPlayerCommand(command, value = null) {
    setError(null);
    try {
      const state = await api.playerCommand(command, value);
      setPlayerState(state);
      if (command === "stop") {
        await refreshMediaCollections();
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function toggleFavorite(item) {
    setError(null);
    try {
      const isFavorite = favoritePaths.has(item.path) || item.favorite;
      await api.setFavorite(item.path, item.title || item.display_title || item.name, !isFavorite);
      await refreshMediaCollections();
      if (browseData) {
        setBrowseData({
          ...browseData,
          items: browseData.items.map((entry) =>
            entry.path === item.path ? { ...entry, favorite: !isFavorite } : entry
          )
        });
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function saveSetting(key, value) {
    const result = await api.setSetting(key, value);
    setSettings((current) => ({ ...current, [result.key]: result.value }));
  }

  async function clearHistory() {
    setError(null);
    try {
      await api.clearHistory();
      setHistory([]);
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function scanLibrary() {
    if (scanning) {
      return;
    }
    setError(null);
    setScanStarting(true);
    try {
      const result = await api.scanLibrary();
      if (result?.id) {
        setScanJob(result);
        if (isFinalScanStatus(result.status)) {
          const [sourceData, mediaData] = await Promise.all([
            api.sources(),
            loadMediaCollections()
          ]);
          setSources(sourceData);
          setLibraryItems(mediaData.libraryItems);
          setHistory(mediaData.history);
          setFavorites(mediaData.favorites);
        }
        return;
      }

      const completedJob = completedScanJobFromSummary(result);
      const [sourceData, mediaData] = await Promise.all([
        api.sources(),
        loadMediaCollections()
      ]);
      setSources(sourceData);
      setLibraryItems(mediaData.libraryItems);
      setHistory(mediaData.history);
      setFavorites(mediaData.favorites);
      setScanJob(completedJob);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setScanStarting(false);
    }
  }

  async function refreshLibraryMetadata() {
    if (metadataRefreshing) {
      return;
    }

    setError(null);
    setMetadataRefreshing(true);
    setMetadataRefresh(metadataRefreshFromSummary({ status: "running" }));
    try {
      const result = await api.refreshMetadata({ force: true });
      const completedRefresh = metadataRefreshFromSummary(result);
      const [sourceData, mediaData] = await Promise.all([
        api.sources(),
        loadMediaCollections()
      ]);
      setSources(sourceData);
      setLibraryItems(mediaData.libraryItems);
      setHistory(mediaData.history);
      setFavorites(mediaData.favorites);
      setMetadataRefresh(completedRefresh);
    } catch (caught) {
      setMetadataRefresh(failedMetadataRefresh(caught.message));
      setError(caught.message);
    } finally {
      setMetadataRefreshing(false);
    }
  }

  async function refreshPlaybackDiagnostics() {
    if (diagnosticsRefreshing) {
      return;
    }

    setError(null);
    setDiagnosticsRefreshing(true);
    try {
      const diagnostics = await api.playbackDiagnostics();
      setHealth(diagnostics);
    } catch (caught) {
      setError(caught.message);
    } finally {
      setDiagnosticsRefreshing(false);
    }
  }

  return (
    <div className="app-shell">
      <Sidebar
        sources={sources}
        activePath={activePath}
        currentView={view}
        onAddFolder={addFolder}
        onOpenSource={openSource}
        onViewChange={setView}
        onScanLibrary={scanLibrary}
        scanning={scanning}
        scanJob={scanJob}
      />

      <main className="workspace">
        <header className="topbar">
          <div className="title-block">
            <span className="eyebrow">StillFrame</span>
            <h1>{viewTitle(view, browseData)}</h1>
          </div>
          <DependencyStatus health={health} />
        </header>

        {error && (
          <div className="notice error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {view === "library" && (
          <FileBrowser
            data={browseData}
            error={browseError}
            favoritePaths={favoritePaths}
            onBack={() => browseData?.parent && openPath(browseData.parent)}
            onOpenDirectory={openPath}
            onPlay={play}
            onToggleFavorite={toggleFavorite}
            onAddFolder={addFolder}
          />
        )}

        {view === "history" && (
          <HistoryList
            title="Recent"
            items={history}
            favoritePaths={favoritePaths}
            onPlay={play}
            onToggleFavorite={toggleFavorite}
            onClear={clearHistory}
          />
        )}

        {view === "index" && (
          <LibraryPage
            items={libraryItems}
            favoritePaths={favoritePaths}
            onPlay={play}
            onToggleFavorite={toggleFavorite}
            onScanLibrary={scanLibrary}
            scanning={scanning}
            scanJob={scanJob}
            onRefreshMetadata={refreshLibraryMetadata}
            metadataRefreshing={metadataRefreshing}
            metadataRefresh={metadataRefresh}
          />
        )}

        {view === "favorites" && (
          <HistoryList
            title="Favorites"
            items={favorites}
            favoritePaths={favoritePaths}
            onPlay={play}
            onToggleFavorite={toggleFavorite}
          />
        )}

        {view === "settings" && (
          <SettingsPage
            health={health}
            settings={settings}
            onSaveSetting={saveSetting}
            onRefreshDiagnostics={refreshPlaybackDiagnostics}
            diagnosticsRefreshing={diagnosticsRefreshing}
          />
        )}
      </main>

      <PlayerPanel state={playerState} onCommand={sendPlayerCommand} />
    </div>
  );
}

function viewTitle(view, browseData) {
  if (view === "history") {
    return "Recent";
  }
  if (view === "index") {
    return "Library";
  }
  if (view === "favorites") {
    return "Favorites";
  }
  if (view === "settings") {
    return "Settings";
  }
  return browseData?.path?.split("/").filter(Boolean).at(-1) || "Library";
}

function DependencyStatus({ health }) {
  if (!health) {
    return <span className="status-chip muted">Starting</span>;
  }

  const ready = health.full_playback_available || (health.mpv_available && health.ffmpeg_available);
  return (
    <div className={`status-chip ${ready ? "ready" : "warning"}`}>
      {ready ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      <span>{ready ? "Ready" : "Needs setup"}</span>
    </div>
  );
}

async function loadMediaCollections() {
  const [libraryData, historyData, favoriteData] = await Promise.all([
    api.library(),
    api.history(),
    api.favorites()
  ]);
  return {
    libraryItems: libraryData.items || [],
    history: historyData,
    favorites: favoriteData
  };
}

function isFinalScanStatus(status) {
  return status === "completed" || status === "failed";
}

function completedScanJobFromSummary(summary) {
  const data = summary || {};
  return {
    id: null,
    status: "completed",
    source_id: data.source_id ?? null,
    limit: data.limit ?? 0,
    items_indexed: data.items_indexed ?? 0,
    sources_scanned: data.sources_scanned ?? 0,
    sources_skipped: data.sources_skipped ?? 0,
    error: null,
    started_at: data.started_at ?? null,
    completed_at: data.completed_at ?? new Date().toISOString()
  };
}

function metadataRefreshFromSummary(summary) {
  const data = summary || {};
  return {
    status: data.status || "completed",
    items_refreshed: Number(data.items_refreshed || 0),
    items_missing: Number(data.items_missing || 0),
    items_skipped: Number(data.items_skipped || 0),
    errors: normalizeMetadataErrors(data.errors),
    error: data.error || null,
    limit: data.limit ?? null
  };
}

function failedMetadataRefresh(message) {
  return metadataRefreshFromSummary({
    status: "failed",
    error: message,
    errors: [message]
  });
}

function normalizeMetadataErrors(errors) {
  if (!errors) {
    return [];
  }
  const list = Array.isArray(errors) ? errors : [errors];
  return list
    .map((entry) => {
      if (!entry) {
        return "";
      }
      if (typeof entry === "string") {
        return entry;
      }
      if (entry.message) {
        return String(entry.message);
      }
      if (entry.error) {
        return String(entry.error);
      }
      try {
        return JSON.stringify(entry);
      } catch {
        return String(entry);
      }
    })
    .filter(Boolean);
}
