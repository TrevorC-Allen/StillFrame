import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2 } from "lucide-react";

import { api } from "../api/client.js";
import { FileBrowser } from "../components/FileBrowser.jsx";
import { HistoryList } from "../components/HistoryList.jsx";
import { PlayerPanel } from "../components/PlayerPanel.jsx";
import { SettingsPage } from "../pages/SettingsPage.jsx";
import { Sidebar } from "../components/Sidebar.jsx";

export default function App() {
  const [health, setHealth] = useState(null);
  const [sources, setSources] = useState([]);
  const [browseData, setBrowseData] = useState(null);
  const [browseError, setBrowseError] = useState(null);
  const [history, setHistory] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [settings, setSettings] = useState({});
  const [playerState, setPlayerState] = useState(null);
  const [view, setView] = useState("library");
  const [activePath, setActivePath] = useState(null);
  const [error, setError] = useState(null);

  const favoritePaths = useMemo(
    () => new Set(favorites.map((favorite) => favorite.path)),
    [favorites]
  );

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

  async function refreshAll() {
    try {
      const [healthData, sourceData, historyData, favoriteData, settingData] = await Promise.all([
        api.health(),
        api.sources(),
        api.history(),
        api.favorites(),
        api.settings()
      ]);
      setHealth(healthData);
      setSources(sourceData);
      setHistory(historyData);
      setFavorites(favoriteData);
      setSettings(settingData);
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
    if (typeof pathOrItem !== "string" && pathOrItem.media_available === false) {
      setError(`${pathOrItem.title || pathOrItem.path}: source is offline.`);
      return;
    }
    setError(null);
    try {
      const state = await api.play(path);
      setPlayerState(state);
      setHistory(await api.history());
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
        setHistory(await api.history());
      }
    } catch (caught) {
      setError(caught.message);
    }
  }

  async function toggleFavorite(item) {
    setError(null);
    try {
      const isFavorite = favoritePaths.has(item.path);
      await api.setFavorite(item.path, item.title || item.name, !isFavorite);
      setFavorites(await api.favorites());
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

  return (
    <div className="app-shell">
      <Sidebar
        sources={sources}
        activePath={activePath}
        currentView={view}
        onAddFolder={addFolder}
        onOpenSource={openSource}
        onViewChange={setView}
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
