from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Optional


SUBTITLE_EXTENSIONS = {".srt", ".ass", ".ssa", ".sub", ".vtt"}
SUBTITLE_DIRS = ("Subs", "subs", "Subtitles", "subtitles")
KNOWN_LANGUAGE_CODES = {
    "chs": "Chinese Simplified",
    "cht": "Chinese Traditional",
    "cn": "Chinese",
    "en": "English",
    "eng": "English",
    "ja": "Japanese",
    "jpn": "Japanese",
    "jp": "Japanese",
    "ko": "Korean",
    "kr": "Korean",
    "zh": "Chinese",
}


class SubtitleManager:
    def match_subtitles(self, media_path: str) -> list[dict[str, Optional[str]]]:
        path = Path(media_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file does not exist: {path}")

        candidates: list[Path] = []
        search_dirs = [path.parent]
        search_dirs.extend(path.parent / name for name in SUBTITLE_DIRS)

        for directory in search_dirs:
            if not directory.exists() or not directory.is_dir():
                continue
            for subtitle in directory.iterdir():
                if subtitle.suffix.lower() not in SUBTITLE_EXTENSIONS:
                    continue
                if self._matches(path, subtitle):
                    candidates.append(subtitle)

        unique = []
        seen = set()
        for candidate in candidates:
            resolved = str(candidate.resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            unique.append(candidate)

        return [self._describe(path, subtitle) for subtitle in unique]

    def _matches(self, media_path: Path, subtitle_path: Path) -> bool:
        media_stem = media_path.stem.lower()
        subtitle_stem = subtitle_path.stem.lower()
        return subtitle_stem == media_stem or subtitle_stem.startswith(f"{media_stem}.")

    def _describe(self, media_path: Path, subtitle_path: Path) -> dict[str, Optional[str]]:
        language = self._guess_language(media_path, subtitle_path)
        return {
            "path": str(subtitle_path),
            "title": subtitle_path.name,
            "format": subtitle_path.suffix.lower().lstrip("."),
            "language": language,
            "encoding": self.detect_encoding(subtitle_path),
        }

    def _guess_language(self, media_path: Path, subtitle_path: Path) -> Optional[str]:
        subtitle_stem = subtitle_path.stem
        suffix = subtitle_stem.removeprefix(media_path.stem).strip(".-_ ").lower()
        if not suffix:
            return None
        token = suffix.split(".")[-1].split("_")[-1].split("-")[-1]
        return KNOWN_LANGUAGE_CODES.get(token, token.upper() if len(token) <= 3 else token)

    def detect_encoding(self, subtitle_path: Path) -> Optional[str]:
        sample = subtitle_path.read_bytes()[:8192]
        for encoding in ("utf-8-sig", "utf-8", "utf-16", "gb18030", "big5"):
            try:
                sample.decode(encoding)
                return encoding
            except UnicodeDecodeError:
                continue
        return None

    def to_webvtt(self, subtitle_path: str, offset: float = 0) -> str:
        path = Path(subtitle_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Subtitle file does not exist: {path}")
        if path.suffix.lower() not in SUBTITLE_EXTENSIONS:
            raise ValueError(f"Unsupported subtitle file: {path}")

        text = self._read_text(path)
        extension = path.suffix.lower()
        if extension == ".vtt":
            webvtt = self._normalize_vtt(text)
        if extension == ".srt":
            webvtt = self._srt_to_vtt(text)
        elif extension in {".ass", ".ssa"}:
            webvtt = self._ass_to_vtt(text)
        elif extension != ".vtt":
            raise ValueError(f"Subtitle format cannot be previewed in browser yet: {extension}")
        return self._shift_webvtt(webvtt, offset) if offset else webvtt

    def _read_text(self, path: Path) -> str:
        raw = path.read_bytes()
        encodings = []
        detected = self.detect_encoding(path)
        if detected:
            encodings.append(detected)
        encodings.extend(["utf-8-sig", "utf-8", "utf-16", "gb18030", "big5"])
        for encoding in dict.fromkeys(encodings):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _normalize_vtt(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        if normalized.lstrip().startswith("WEBVTT"):
            return normalized
        return f"WEBVTT\n\n{normalized}"

    def _srt_to_vtt(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        normalized = re.sub(
            r"(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})",
            r"\1.\2 --> \3.\4",
            normalized,
        )
        lines = []
        for line in normalized.split("\n"):
            if line.strip().isdigit():
                continue
            lines.append(line)
        return "WEBVTT\n\n" + "\n".join(lines).strip() + "\n"

    def _ass_to_vtt(self, text: str) -> str:
        normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        events_started = False
        fields: list[str] = []
        cues: list[str] = []

        for raw_line in normalized.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.lower() == "[events]":
                events_started = True
                continue
            if not events_started:
                continue
            if line.lower().startswith("format:"):
                fields = [part.strip().lower() for part in line.split(":", 1)[1].split(",")]
                continue
            if not line.lower().startswith("dialogue:") or not fields:
                continue

            values = line.split(":", 1)[1].split(",", len(fields) - 1)
            if len(values) < len(fields):
                continue
            data = dict(zip(fields, values))
            start = self._ass_timestamp_to_vtt(data.get("start", "").strip())
            end = self._ass_timestamp_to_vtt(data.get("end", "").strip())
            body = self._clean_ass_text(data.get("text", ""))
            if start and end and body:
                cues.append(f"{start} --> {end}\n{body}")

        return "WEBVTT\n\n" + "\n\n".join(cues) + "\n"

    def _ass_timestamp_to_vtt(self, value: str) -> Optional[str]:
        match = re.match(r"(?:(\d+):)?(\d{1,2}):(\d{2})[.](\d{1,2})", value)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        centiseconds = match.group(4).ljust(2, "0")[:2]
        return f"{hours:02}:{minutes:02}:{seconds:02}.{centiseconds}0"

    def _clean_ass_text(self, value: str) -> str:
        value = re.sub(r"\{[^}]*\}", "", value)
        value = value.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ")
        return html.unescape(value).strip()

    def _shift_webvtt(self, text: str, offset: float) -> str:
        def replace(match: re.Match[str]) -> str:
            start = self._shift_vtt_timestamp(match.group(1), offset)
            end = self._shift_vtt_timestamp(match.group(2), offset)
            return f"{start} --> {end}"

        return re.sub(
            r"(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})",
            replace,
            text,
        )

    def _shift_vtt_timestamp(self, value: str, offset: float) -> str:
        hours, minutes, rest = value.split(":")
        seconds, millis = rest.split(".")
        total = (
            int(hours) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(millis) / 1000
            + offset
        )
        total = max(total, 0)
        whole = int(total)
        milliseconds = int(round((total - whole) * 1000))
        if milliseconds == 1000:
            whole += 1
            milliseconds = 0
        shifted_hours = whole // 3600
        shifted_minutes = (whole % 3600) // 60
        shifted_seconds = whole % 60
        return f"{shifted_hours:02}:{shifted_minutes:02}:{shifted_seconds:02}.{milliseconds:03}"
