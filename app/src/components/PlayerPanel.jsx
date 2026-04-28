import { Pause, Play, Square } from "lucide-react";
import { useEffect, useState } from "react";

export function PlayerPanel({ state, onCommand }) {
  const [seekValue, setSeekValue] = useState(0);

  useEffect(() => {
    setSeekValue(Math.round(state?.position || 0));
  }, [state?.position]);

  const duration = Math.round(state?.duration || 0);
  const running = Boolean(state?.running);

  return (
    <aside className="player-panel">
      <div className="now-playing">
        <span className="eyebrow">Now Playing</span>
        <h2>{state?.title || "Idle"}</h2>
        {state?.error && <p className="panel-error">{state.error}</p>}
      </div>

      <div className="transport">
        <button
          className="round-button"
          disabled={!running}
          onClick={() => onCommand(state?.paused ? "resume" : "pause")}
          title={state?.paused ? "Resume" : "Pause"}
        >
          {state?.paused ? <Play size={22} /> : <Pause size={22} />}
        </button>
        <button
          className="round-button secondary"
          disabled={!running}
          onClick={() => onCommand("stop")}
          title="Stop"
        >
          <Square size={20} />
        </button>
      </div>

      <div className="seek-control">
        <span>{formatTime(seekValue)}</span>
        <input
          type="range"
          min="0"
          max={duration || 0}
          value={seekValue}
          disabled={!duration}
          onChange={(event) => setSeekValue(Number(event.target.value))}
          onMouseUp={() => onCommand("seek", seekValue)}
          onKeyUp={() => onCommand("seek", seekValue)}
        />
        <span>{formatTime(duration)}</span>
      </div>

      <label className="field">
        <span>Speed</span>
        <select disabled={!running} onChange={(event) => onCommand("set_speed", event.target.value)} defaultValue="1">
          <option value="0.5">0.5x</option>
          <option value="0.75">0.75x</option>
          <option value="1">1x</option>
          <option value="1.25">1.25x</option>
          <option value="1.5">1.5x</option>
          <option value="2">2x</option>
        </select>
      </label>

      <label className="field">
        <span>Audio</span>
        <select
          disabled={!running || !state?.audio_tracks?.length}
          value={state?.selected_audio || ""}
          onChange={(event) => onCommand("select_audio", Number(event.target.value))}
        >
          <option value="">Auto</option>
          {state?.audio_tracks?.map((track) => (
            <option key={track.id} value={track.id}>
              {track.title || track.lang || `Track ${track.id}`}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Subtitle</span>
        <select
          disabled={!running || !state?.subtitle_tracks?.length}
          value={state?.selected_subtitle || ""}
          onChange={(event) => onCommand("select_subtitle", event.target.value === "" ? "no" : Number(event.target.value))}
        >
          <option value="">Off</option>
          {state?.subtitle_tracks?.map((track) => (
            <option key={track.id} value={track.id}>
              {track.title || track.lang || `Track ${track.id}`}
            </option>
          ))}
        </select>
      </label>
    </aside>
  );
}

function formatTime(seconds) {
  if (!seconds) {
    return "00:00";
  }
  const whole = Math.max(0, Math.floor(seconds));
  const mins = Math.floor(whole / 60);
  const secs = whole % 60;
  const hours = Math.floor(mins / 60);
  const minutes = mins % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

