import { Play, Star } from "lucide-react";

export function HistoryList({ title, items, favoritePaths, onPlay, onToggleFavorite, onClear }) {
  return (
    <section className="list-view">
      <div className="section-head">
        <h2>{title}</h2>
        {onClear ? (
          <button className="text-button" onClick={onClear} disabled={items.length === 0}>
            Clear
          </button>
        ) : (
          <span>{items.length}</span>
        )}
      </div>

      <div className="file-table">
        {items.length === 0 && (
          <div className="empty-state compact">
            <span>No items yet.</span>
          </div>
        )}
        {items.map((item) => (
          <div className={item.media_available === false ? "file-row offline" : "file-row"} key={item.path}>
            <button className="file-main" onClick={() => onPlay(item)}>
              <Play size={20} />
              <span>{item.title || item.path.split("/").at(-1)}</span>
            </button>
            <span className="muted-text">{item.media_available === false ? "Offline" : formatProgress(item)}</span>
            <button
              className={favoritePaths.has(item.path) ? "icon-button active" : "icon-button"}
              onClick={() => onToggleFavorite(item)}
              title="Favorite"
            >
              <Star size={17} />
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatProgress(item) {
  if (!item.duration) {
    return "";
  }
  return `${Math.round((item.position / item.duration) * 100)}%`;
}
