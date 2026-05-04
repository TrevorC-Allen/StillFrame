import { useMemo, useState } from "react";
import { ChevronLeft, Film, Folder, Play, Plus, Star } from "lucide-react";

import { mediaUrl } from "../api/client.js";

export function FileBrowser({
  data,
  error,
  favoritePaths,
  onBack,
  onOpenDirectory,
  onPlay,
  onToggleFavorite,
  onAddFolder
}) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("name");
  const visibleItems = useMemo(() => filterAndSortItems(data?.items || [], filter, sort), [data, filter, sort]);

  if (error) {
    return (
      <section className="empty-state">
        <div className="empty-card">
          <strong>Folder unavailable</strong>
          <p>{error.message}</p>
          <small>{error.path}</small>
          <button className="primary-button" onClick={onAddFolder}>
            <Plus size={18} />
            <span>Choose Folder</span>
          </button>
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="empty-state">
        <button className="primary-button" onClick={onAddFolder}>
          <Plus size={18} />
          <span>Add Folder</span>
        </button>
      </section>
    );
  }

  return (
    <section className="browser">
      <div className="pathbar">
        <button className="icon-button" onClick={onBack} disabled={!data.parent} title="Back">
          <ChevronLeft size={18} />
        </button>
        <span>{data.path}</span>
        <input
          className="browser-filter"
          type="search"
          placeholder="Filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        <select
          className="browser-sort"
          value={sort}
          onChange={(event) => setSort(event.target.value)}
          aria-label="Sort current folder"
        >
          <option value="name">Name</option>
          <option value="recent">Recently Modified</option>
          <option value="size">Size</option>
          <option value="type">Type</option>
        </select>
      </div>

      <div className="file-table">
        {data.items.length === 0 && (
          <div className="empty-state compact">
            <span>No folders or supported videos in this folder.</span>
          </div>
        )}
        {data.items.length > 0 && visibleItems.length === 0 && (
          <div className="empty-state compact">
            <span>No matches.</span>
          </div>
        )}
        {visibleItems.map((item) => (
          <div className="file-row" key={item.path}>
            <button
              className={item.kind === "video" ? "file-main rich" : "file-main"}
              onClick={() =>
                item.kind === "directory" ? onOpenDirectory(item.path) : onPlay(item.path)
              }
            >
              {item.kind === "directory" ? <Folder size={20} /> : <FilePoster item={item} />}
              {item.kind === "directory" ? (
                <span>{item.name}</span>
              ) : (
                <span className="file-copy">
                  <strong>{displayTitle(item)}</strong>
                  <small>{fileSubtitle(item)}</small>
                  {item.overview && <small className="file-overview">{item.overview}</small>}
                </span>
              )}
            </button>

            {item.kind === "video" && (
              <>
                <div className="progress-cell">
                  {item.progress ? <Progress value={item.progress} /> : <span />}
                </div>
                <span className="muted-text">{formatBytes(item.size)}</span>
                <button
                  className={favoritePaths.has(item.path) || item.favorite ? "icon-button active" : "icon-button"}
                  onClick={() => onToggleFavorite(item)}
                  title="Favorite"
                >
                  <Star size={17} />
                </button>
              </>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function filterAndSortItems(items, filter, sort) {
  const query = filter.trim().toLowerCase();
  const filtered = query
    ? items.filter((item) =>
        `${item.name || ""} ${item.display_title || ""} ${item.title || ""} ${item.year || ""} ${item.quality || ""} ${item.media_type || ""} ${item.overview || ""}`
          .toLowerCase()
          .includes(query)
      )
    : [...items];

  return filtered.sort((a, b) => {
    const folderOrder = (a.kind === "directory" ? 0 : 1) - (b.kind === "directory" ? 0 : 1);
    if (sort === "recent") {
      return folderOrder || (b.modified_at || 0) - (a.modified_at || 0) || a.name.localeCompare(b.name);
    }
    if (sort === "size") {
      return folderOrder || (b.size || 0) - (a.size || 0) || a.name.localeCompare(b.name);
    }
    if (sort === "type") {
      return a.kind.localeCompare(b.kind) || a.name.localeCompare(b.name);
    }
    return folderOrder || a.name.localeCompare(b.name);
  });
}

function FilePoster({ item }) {
  const src = mediaUrl(item.artwork_url);
  return (
    <span className="file-thumb">
      {src ? <img src={src} alt="" /> : <Film size={20} />}
    </span>
  );
}

function displayTitle(item) {
  return item.display_title || item.title || item.name || "Untitled";
}

function fileSubtitle(item) {
  const parts = [];
  if (item.media_type) {
    parts.push(item.media_type === "tv" ? "TV" : item.media_type === "movie" ? "Movie" : item.media_type);
  }
  if (item.year) {
    parts.push(item.year);
  }
  if (item.season && item.episode) {
    parts.push(`S${String(item.season).padStart(2, "0")}E${String(item.episode).padStart(2, "0")}`);
  }
  if (item.quality) {
    parts.push(item.quality);
  }
  return parts.join(" / ") || item.name;
}

function Progress({ value }) {
  return (
    <div className="progress-track">
      <span style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

function formatBytes(size) {
  if (!size) {
    return "";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = size;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
