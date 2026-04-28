import { CheckCircle2, XCircle } from "lucide-react";

export function SettingsPage({ health, settings, onSaveSetting }) {
  return (
    <section className="settings-grid">
      <div className="settings-panel">
        <h2>Runtime</h2>
        <DependencyLine label="mpv" ready={health?.mpv_available} path={health?.mpv_path} />
        <DependencyLine label="ffmpeg" ready={health?.ffmpeg_available} path={health?.ffmpeg_path} />
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
    </section>
  );
}

function DependencyLine({ label, ready, path }) {
  return (
    <div className="setting-row">
      <span>{label}</span>
      <div className="dependency-stack">
        <span className={ready ? "dependency ready" : "dependency missing"}>
          {ready ? <CheckCircle2 size={17} /> : <XCircle size={17} />}
          {ready ? "Available" : "Missing"}
        </span>
        {path && <code>{path}</code>}
      </div>
    </div>
  );
}
