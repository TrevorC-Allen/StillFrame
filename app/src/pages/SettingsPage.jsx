import { AlertCircle, CheckCircle2, RefreshCw, XCircle } from "lucide-react";

export function SettingsPage({
  health,
  cacheDiagnostics,
  settings,
  onSaveSetting,
  onRefreshDiagnostics,
  diagnosticsRefreshing = false,
  onRefreshCacheDiagnostics,
  cacheRefreshing = false
}) {
  const ready = playbackReady(health);
  const issues = health?.issues || [];

  return (
    <section className="settings-grid">
      <div className="settings-panel playback-diagnostics-panel">
        <div className="settings-panel-head">
          <div>
            <h2>Playback Diagnostics</h2>
            <span>{diagnosticsSourceLabel(health)} · {health?.platform || "Unknown platform"}</span>
          </div>
          <button
            className="text-button diagnostics-refresh-button"
            type="button"
            onClick={onRefreshDiagnostics}
            disabled={diagnosticsRefreshing}
          >
            <RefreshCw size={15} className={diagnosticsRefreshing ? "spinning" : ""} />
            <span>{diagnosticsRefreshing ? "Refreshing" : "Refresh Diagnostics"}</span>
          </button>
        </div>

        <div className={`diagnostic-summary ${ready ? "ready" : "warning"}`}>
          {ready ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
          <span>{ready ? "Full playback available" : "Playback setup needs attention"}</span>
        </div>

        <DiagnosticTool label="mpv" tool={health?.mpv} ready={health?.mpv_available} path={health?.mpv_path} version={health?.mpv_version} />
        <DiagnosticTool label="ffmpeg" tool={health?.ffmpeg} ready={health?.ffmpeg_available} path={health?.ffmpeg_path} version={health?.ffmpeg_version} />

        {issues.length > 0 && (
          <div className="diagnostic-issues">
            <strong>Issues</strong>
            {issues.map((issue, index) => (
              <div className="diagnostic-issue" key={`${issue.code || issue.message || "issue"}-${index}`}>
                <span>{issue.message || "Playback issue detected."}</span>
                {issue.action && <small>Action: {issue.action}</small>}
              </div>
            ))}
          </div>
        )}

        {health?.install_hint && (
          <p className="runtime-hint">{health.install_hint}</p>
        )}
        <div className="setting-row">
          <span>Database</span>
          <code>{health?.database_path || ""}</code>
        </div>
      </div>

      <div className="settings-panel">
        <h2>Playback</h2>
        <label className="field">
          <span>Resume</span>
          <select
            value={settings.resume || "on"}
            onChange={(event) => onSaveSetting("resume", event.target.value)}
          >
            <option value="on">On</option>
            <option value="off">Off</option>
          </select>
        </label>
        <label className="field">
          <span>Subtitle encoding</span>
          <select
            value={settings.subtitle_encoding || "auto"}
            onChange={(event) => onSaveSetting("subtitle_encoding", event.target.value)}
          >
            <option value="auto">Auto</option>
            <option value="utf-8">UTF-8</option>
            <option value="gb18030">GB18030</option>
            <option value="big5">Big5</option>
          </select>
        </label>
      </div>

      <div className="settings-panel cache-diagnostics-panel">
        <div className="settings-panel-head">
          <div>
            <h2>Media Cache</h2>
            <span>{cacheDiagnostics?.root || "Cache diagnostics pending"}</span>
          </div>
          <button
            className="text-button diagnostics-refresh-button"
            type="button"
            onClick={onRefreshCacheDiagnostics}
            disabled={cacheRefreshing}
          >
            <RefreshCw size={15} className={cacheRefreshing ? "spinning" : ""} />
            <span>{cacheRefreshing ? "Refreshing" : "Refresh Cache"}</span>
          </button>
        </div>

        <div className="cache-summary">
          <span>Total files <strong>{formatCount(cacheDiagnostics?.total_files)}</strong></span>
          <span>Storage <strong>{formatBytes(cacheDiagnostics?.total_bytes)}</strong></span>
        </div>

        <div className="cache-buckets">
          {(cacheDiagnostics?.buckets || []).map((bucket) => (
            <div className={bucket.exists ? "cache-bucket" : "cache-bucket missing"} key={bucket.name}>
              <div>
                <strong>{bucket.name}</strong>
                <small>{bucket.path}</small>
              </div>
              <span>{formatCount(bucket.files)} files</span>
              <span>{formatBytes(bucket.bytes)}</span>
            </div>
          ))}
          {!cacheDiagnostics && <span className="runtime-hint">Cache diagnostics are not loaded yet.</span>}
        </div>
      </div>
    </section>
  );
}

function DiagnosticTool({ label, tool, ready, path, version }) {
  const normalized = {
    present: tool?.present ?? Boolean(ready),
    path: tool?.path ?? path ?? null,
    version: tool?.version ?? version ?? null
  };

  return (
    <div className={`diagnostic-tool ${normalized.present ? "ready" : "missing"}`}>
      <div className="diagnostic-tool-name">
        <span className={normalized.present ? "dependency ready" : "dependency missing"}>
          {normalized.present ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
          {label}
        </span>
      </div>
      <div className="dependency-stack">
        <span>{normalized.present ? (normalized.version || "Available") : "Missing"}</span>
        {normalized.path && <code>{normalized.path}</code>}
      </div>
    </div>
  );
}

function playbackReady(health) {
  return Boolean(health?.full_playback_available || (health?.mpv_available && health?.ffmpeg_available));
}

function diagnosticsSourceLabel(health) {
  if (!health) {
    return "Diagnostics pending";
  }
  return health.diagnostics_source === "health" ? "/health fallback" : "/diagnostics/playback";
}

function formatCount(value) {
  return Number(value || 0).toLocaleString();
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (!value) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB", "TB"];
  let amount = value;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
