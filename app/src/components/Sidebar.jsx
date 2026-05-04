import { AlertCircle, AlertTriangle, CheckCircle2, Clock, FolderOpen, Library, Plus, RefreshCw, Settings, Star } from "lucide-react";

export function Sidebar({
  sources,
  activePath,
  currentView,
  onAddFolder,
  onOpenSource,
  onViewChange,
  onScanLibrary,
  scanning,
  scanJob
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
          <Library size={18} />
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
          <button className="icon-button" onClick={onScanLibrary} disabled={scanning} title="Scan library">
            <RefreshCw size={17} className={scanning ? "spinning" : ""} />
          </button>
          <button className="icon-button" onClick={onAddFolder} title="Add folder">
            <Plus size={17} />
          </button>
        </span>
      </div>

      <SidebarScanStatus job={scanJob} />

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

function SidebarScanStatus({ job }) {
  if (!job) {
    return null;
  }

  const Icon = job.status === "completed" ? CheckCircle2 : job.status === "failed" ? AlertCircle : RefreshCw;
  return (
    <div className={`sidebar-scan ${job.status}`}>
      <span className="sidebar-scan-title">
        <Icon size={15} className={job.status === "running" ? "spinning" : ""} />
        <strong>{scanStatusLabel(job.status)}</strong>
      </span>
      <span>{formatCount(job.items_indexed)} indexed</span>
      <span>{formatCount(job.sources_skipped)} skipped</span>
      {job.error && <span className="sidebar-scan-error">{job.error}</span>}
    </div>
  );
}

function scanStatusLabel(status) {
  if (status === "completed") {
    return "Scan completed";
  }
  if (status === "failed") {
    return "Scan failed";
  }
  return "Scan running";
}

function formatCount(value) {
  return Number.isFinite(value) ? value : 0;
}
