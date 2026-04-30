import { AlertTriangle, Clock, FolderOpen, Plus, Settings, Star } from "lucide-react";

export function Sidebar({
  sources,
  activePath,
  currentView,
  onAddFolder,
  onOpenSource,
  onViewChange,
  onScanLibrary
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">
          <img src="/stillframe-mark.svg" alt="" />
        </div>
        <span>StillFrame</span>
      </div>

      <nav className="nav-group">
        <button
          className={currentView === "index" ? "nav-item active" : "nav-item"}
          onClick={() => onViewChange("index")}
        >
          <FolderOpen size={18} />
          <span>Library</span>
        </button>
        <button
          className={currentView === "history" ? "nav-item active" : "nav-item"}
          onClick={() => onViewChange("history")}
        >
          <Clock size={18} />
          <span>Recent</span>
        </button>
        <button
          className={currentView === "favorites" ? "nav-item active" : "nav-item"}
          onClick={() => onViewChange("favorites")}
        >
          <Star size={18} />
          <span>Favorites</span>
        </button>
        <button
          className={currentView === "settings" ? "nav-item active" : "nav-item"}
          onClick={() => onViewChange("settings")}
        >
          <Settings size={18} />
          <span>Settings</span>
        </button>
      </nav>

      <div className="source-header">
        <span>Sources</span>
        <span className="source-tools">
          <button className="icon-button" onClick={onScanLibrary} title="Scan library">
            <FolderOpen size={17} />
          </button>
          <button className="icon-button" onClick={onAddFolder} title="Add folder">
            <Plus size={17} />
          </button>
        </span>
      </div>

      <div className="source-list">
        {sources.map((source) => (
          <button
            key={source.id}
            className={
              activePath && activePath.startsWith(source.path)
                ? `source-item active ${source.available === false ? "offline" : ""}`
                : `source-item ${source.available === false ? "offline" : ""}`
            }
            title={source.available === false ? source.last_error : source.path}
            onClick={() => onOpenSource(source)}
          >
            {source.available === false ? <AlertTriangle size={17} /> : <FolderOpen size={17} />}
            <span>{source.name}</span>
          </button>
        ))}
        {sources.length === 0 && (
          <div className="sidebar-empty">Add a local folder or a mounted NAS share.</div>
        )}
      </div>
    </aside>
  );
}
