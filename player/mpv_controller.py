from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional


class MPVUnavailableError(RuntimeError):
    pass


class MPVController:
    def __init__(self) -> None:
        self.process: Optional[subprocess.Popen[str]] = None
        self.ipc_path = Path(tempfile.gettempdir()) / f"stillframe-mpv-{os.getpid()}.sock"
        self.state: dict[str, Any] = {
            "path": None,
            "title": None,
            "duration": 0,
            "position": 0,
            "paused": False,
            "audio_tracks": [],
            "subtitle_tracks": [],
            "selected_audio": None,
            "selected_subtitle": None,
            "error": None,
            "ended": False,
            "running": False,
        }

    def open(self, media_path: str, *, start_position: float = 0, subtitles: Optional[list[str]] = None) -> dict[str, Any]:
        path = Path(media_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file does not exist: {path}")

        mpv = shutil.which("mpv")
        if not mpv:
            self.state["error"] = "mpv is not installed or not on PATH"
            raise MPVUnavailableError(self.state["error"])

        self.stop()
        try:
            self.ipc_path.unlink(missing_ok=True)
        except OSError:
            pass

        args = [
            mpv,
            "--force-window=yes",
            "--idle=no",
            f"--input-ipc-server={self.ipc_path}",
            "--hwdec=auto-safe",
            "--vo=gpu-next",
            "--profile=high-quality",
            "--save-position-on-quit=no",
            "--keep-open=no",
        ]
        if start_position > 1:
            args.append(f"--start={start_position}")
        for subtitle in subtitles or []:
            args.append(f"--sub-file={subtitle}")
        args.append(str(path))

        self.process = subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

        self.state.update(
            {
                "path": str(path),
                "title": path.stem,
                "duration": 0,
                "position": start_position,
                "paused": False,
                "audio_tracks": [],
                "subtitle_tracks": [],
                "selected_audio": None,
                "selected_subtitle": None,
                "error": None,
                "ended": False,
                "running": True,
            }
        )
        self._wait_for_ipc()
        return self.get_state()

    def get_state(self) -> dict[str, Any]:
        if self.process and self.process.poll() is not None:
            self.state["running"] = False
            self.state["ended"] = True
            return dict(self.state)

        if not self.process:
            self.state["running"] = False
            return dict(self.state)

        try:
            duration = self._get_property("duration")
            position = self._get_property("time-pos")
            paused = self._get_property("pause")
            tracks = self._get_property("track-list") or []
            aid = self._get_property("aid")
            sid = self._get_property("sid")
        except OSError as exc:
            self.state["error"] = str(exc)
            return dict(self.state)

        audio_tracks = [track for track in tracks if track.get("type") == "audio"]
        subtitle_tracks = [track for track in tracks if track.get("type") == "sub"]
        self.state.update(
            {
                "duration": float(duration or 0),
                "position": float(position or 0),
                "paused": bool(paused),
                "audio_tracks": audio_tracks,
                "subtitle_tracks": subtitle_tracks,
                "selected_audio": aid,
                "selected_subtitle": sid,
                "running": True,
                "error": None,
            }
        )
        return dict(self.state)

    def command(self, name: str, value: Any = None) -> dict[str, Any]:
        if name == "pause":
            self._send(["set_property", "pause", True])
        elif name == "resume":
            self._send(["set_property", "pause", False])
        elif name == "seek":
            self._send(["seek", float(value or 0), "absolute"])
        elif name == "set_speed":
            self._send(["set_property", "speed", float(value or 1)])
        elif name == "select_audio":
            self._send(["set_property", "aid", value])
        elif name == "select_subtitle":
            self._send(["set_property", "sid", value])
        elif name == "set_sub_delay":
            self._send(["set_property", "sub-delay", float(value or 0)])
        elif name == "stop":
            self.stop()
            return dict(self.state)
        else:
            raise ValueError(f"Unsupported player command: {name}")
        return self.get_state()

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                self._send(["quit"])
            except OSError:
                self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None
        self.state["running"] = False

    def _wait_for_ipc(self) -> None:
        deadline = time.time() + 3
        while time.time() < deadline:
            if self.ipc_path.exists():
                return
            if self.process and self.process.poll() is not None:
                raise RuntimeError("mpv exited before IPC became available")
            time.sleep(0.05)

    def _get_property(self, name: str) -> Any:
        response = self._send(["get_property", name])
        return response.get("data")

    def _send(self, command: list[Any]) -> dict[str, Any]:
        if not self.ipc_path.exists():
            raise OSError("mpv IPC socket is not available")

        payload = json.dumps({"command": command}).encode("utf-8") + b"\n"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1)
            client.connect(str(self.ipc_path))
            client.sendall(payload)
            raw = b""
            while not raw.endswith(b"\n"):
                chunk = client.recv(4096)
                if not chunk:
                    break
                raw += chunk
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

