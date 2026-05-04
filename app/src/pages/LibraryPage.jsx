import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, Film, Play, RefreshCw, Search, Star } from "lucide-react";

import { mediaUrl } from "../api/client.js";

export function LibraryPage({
  items,
  favoritePaths,
  onPlay,
  onToggleFavorite,
  onScanLibrary,
  scanning,
  scanJob
}) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("recent");
  const [selectedPath, setSelectedPath] = useState(null);

  const visibleItems = useMemo(
    () => filterAndSortItems(items, filter, sort),
    [items, filter, sort]
  );

  const selectedItem = visibleItems.find((item) => item.path === selectedPath) || visibleItems[0] || null;

  useEffect(() => {
    if (!selectedItem) {
      setSelectedPath(null);
      return;
    }
    if (selectedItem.path !== selectedPath) {
      setSelectedPath(selectedItem.path);
    }
  }, [selectedItem, selectedPath]);

  return (
    <section className="library-page">
      <div className="library-toolbar">
        <div className="library-heading">
          <h2>Indexed Library</h2>
          <span>{visibleItems.length} of {items.length}</span>
        </div>
        <label className="library-search">
          <Search size={16} />
          <input
            type="search"
            placeholder="Search"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
        </label>
        <select
          className="library-sort"
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          aria-label="Sort library"
        >
          <option value="recent">Recently Modified</option>
          <option value="title">Title</option>
          <option value="year">Year</option>
          <option value="quality">Quality</option>
        </select>
        <button className="primary-button scan-button" onClick={onScanLibrary} disabled={scanning}>
          <RefreshCw size={17} className={scanning ? "spinning" : ""} />
          <span>{scanning ? "Scanning" : "Scan Library"}</span>
        </button>
      </div>

      <ScanJobStatus job={scanJob} />

      <div className="library-layout">
        <div className="library-list">
          {items.length === 0 && (
            <div className="empty-state compact">
              <span>Scan your connected sources to build the local library index.</span>
            </div>
          )}
          {items.length > 0 && visibleItems.length === 0 && (
            <div className="empty-state compact">
              <span>No library matches.</span>
            </div>
          )}
          {visibleItems.map((item) => (
            <LibraryRow
              key={item.path}
              item={item}
              favorite={favoritePaths.has(item.path) || item.favorite}
              selected={selectedItem?.path === item.path}
              onSelect={() => setSelectedPath(item.path)}
              onPlay={() => onPlay(item)}
              onToggleFavorite={() => onToggleFavorite(item)}
            />
          ))}
        </div>

        <LibraryPreview
          item={selectedItem}
          favorite={selectedItem ? favoritePaths.has(selectedItem.path) || selectedItem.favorite : false}
          onPlay={onPlay}
          onToggleFavorite={onToggleFavorite}
        />
      </div>
    </section>
  );
}

function ScanJobStatus({ job }) {
  if (!job) {
    return null;
  }

  const Icon = job.status === "completed" ? CheckCircle2 : job.status === "failed" ? AlertCircle : RefreshCw;
  return (
    <div className={`scan-note ${job.status}`}>
      <span className="scan-note-header">
        <Icon size={17} className={job.status === "running" ? "spinning" : ""} />
        <strong>Status: {scanStatusLabel(job.status)}</strong>
      </span>
      <span className="scan-stat">{formatCount(job.items_indexed)} indexed</span>
      <span className="scan-stat">{formatCount(job.sources_scanned)} scanned</span>
      <span className="scan-stat">{formatCount(job.sources_skipped)} skipped</span>
      {job.error && <span className="scan-error">Error: {job.error}</span>}
    </div>
  );
}

function LibraryRow({ item, favorite, selected, onSelect, onPlay, onToggleFavorite }) {
  const online = item.available !== false && item.media_available !== false;
  const title = displayTitle(item);

  return (
    <div className={`library-row ${selected ? "selected" : ""} ${online ? "" : "offline"}`}>
      <button className="library-select" type="button" onClick={onSelect} onDoubleClick={online ? onPlay : undefined}>
        <PosterThumb item={item} />
        <span className="library-copy">
          <strong>{title}</strong>
          <span className="library-badges">
            <span>{item.year || "Unknown year"}</span>
            <span>{item.quality || mediaTypeLabel(item.media_type) || "Video"}</span>
            <span className={online ? "online-pill" : "offline-pill"}>{online ? "Online" : "Offline"}</span>
            {favorite && <span className="favorite-pill">Favorite</span>}
          </span>
          {item.overview && <span className="library-overview">{item.overview}</span>}
        </span>
      </button>
      <button className="icon-button" type="button" onClick={onPlay} disabled={!online} title="Play">
        <Play size={17} />
      </button>
      <button
        className={favorite ? "icon-button active" : "icon-button"}
        type="button"
        onClick={onToggleFavorite}
        title={favorite ? "Remove favorite" : "Favorite"}
      >
        <Star size={17} />
      </button>
    </div>
  );
}

function LibraryPreview({ item, favorite, onPlay, onToggleFavorite }) {
  if (!item) {
    return (
      <aside className="library-preview empty-preview">
        <Film size={34} />
        <span>No library item selected.</span>
      </aside>
    );
  }

  const online = item.available !== false && item.media_available !== false;
  const posterSrc = mediaUrl(item.artwork_url);

  return (
    <aside className="library-preview">
      <div className="poster-frame">
        {posterSrc ? <img src={posterSrc} alt="" /> : <Film size={42} />}
      </div>

      <div className="preview-title">
        <h2>{displayTitle(item)}</h2>
        <span>{librarySubtitle(item)}</span>
      </div>

      <div className="preview-actions">
        <button className="primary-button" type="button" onClick={() => onPlay(item)} disabled={!online}>
          <Play size={17} />
          <span>Play</span>
        </button>
        <button
          className={favorite ? "text-button active" : "text-button"}
          type="button"
          onClick={() => onToggleFavorite(item)}
        >
          <Star size={16} />
          <span>{favorite ? "Favorited" : "Favorite"}</span>
        </button>
      </div>

      <p className="preview-overview">{item.overview || "No overview is available for this item yet."}</p>

      <dl className="metadata-grid">
        <dt>Status</dt>
        <dd>{online ? "Online" : "Offline"}</dd>
        <dt>Quality</dt>
        <dd>{item.quality || "Unknown"}</dd>
        <dt>Type</dt>
        <dd>{mediaTypeLabel(item.media_type) || "Video"}</dd>
        <dt>Metadata</dt>
        <dd>{metadataSourceLabel(item.metadata_source)}</dd>
      </dl>

      <div className="path-block">
        <span>Path</span>
        <code>{item.path}</code>
      </div>
      {item.source_path && (
        <div className="path-block">
          <span>Source</span>
          <code>{item.source_path}</code>
        </div>
      )}
    </aside>
  );
}

function PosterThumb({ item }) {
  const posterSrc = mediaUrl(item.artwork_url);
  return (
    <span className="library-thumb">
      {posterSrc ? <img src={posterSrc} alt="" /> : <Film size={20} />}
    </span>
  );
}

function filterAndSortItems(items, filter, sort) {
  const query = filter.trim().toLowerCase();
  const filtered = query
    ? items.filter((item) =>
        [
          displayTitle(item),
          item.name,
          item.year,
          item.quality,
          item.overview,
          item.path,
          item.source_path,
          item.metadata_source,
          item.media_type
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(query)
      )
    : [...items];

  return filtered.sort((a, b) => {
    if (sort === "title") {
      return displayTitle(a).localeCompare(displayTitle(b));
    }
    if (sort === "year") {
      return (b.year || 0) - (a.year || 0) || displayTitle(a).localeCompare(displayTitle(b));
    }
    if (sort === "quality") {
      return (a.quality || "").localeCompare(b.quality || "") || displayTitle(a).localeCompare(displayTitle(b));
    }
    return (b.modified_at || 0) - (a.modified_at || 0) || displayTitle(a).localeCompare(displayTitle(b));
  });
}

function displayTitle(item) {
  return item.display_title || item.title || item.name || item.path.split("/").at(-1);
}

function librarySubtitle(item) {
  const parts = [];
  if (item.year) {
    parts.push(item.year);
  }
  if (item.season && item.episode) {
    parts.push(`S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`);
  }
  if (item.position && item.duration) {
    parts.push(`${Math.round((item.position / item.duration) * 100)}% watched`);
  }
  const folder = item.source_path ? item.source_path.split("/").filter(Boolean).at(-1) : "";
  if (folder) {
    parts.push(folder);
  }
  return parts.join(" / ") || item.name || "";
}

function mediaTypeLabel(mediaType) {
  if (mediaType === "tv") {
    return "TV";
  }
  if (mediaType === "movie") {
    return "Movie";
  }
  return mediaType;
}

function metadataSourceLabel(source) {
  if (source === "tmdb") {
    return "TMDb";
  }
  if (source === "local") {
    return "Local";
  }
  return source || "Unknown";
}

function scanStatusLabel(status) {
  if (status === "completed") {
    return "Completed";
  }
  if (status === "failed") {
    return "Failed";
  }
  return "Running";
}

function formatCount(value) {
  return Number.isFinite(value) ? value : 0;
}
