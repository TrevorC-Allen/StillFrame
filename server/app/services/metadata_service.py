from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import html
import re
import shutil
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import MEDIA_CACHE_DIR, TMDB_API_KEY, TMDB_BEARER_TOKEN, TMDB_LANGUAGE
from app.services.library_service import utc_now


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"
MAX_RELEASE_YEAR = datetime.now(timezone.utc).year + 2

YEAR_PATTERN = re.compile(r"(?<!\d)((?:18[89]\d|19\d{2}|20\d{2}))(?!\d)")
EPISODE_PATTERN = re.compile(r"\bS(\d{1,2})E(\d{1,3})\b", re.IGNORECASE)
CHINESE_EPISODE_PATTERN = re.compile(r"第\s*(\d{1,2})\s*季\s*第\s*(\d{1,3})\s*[集话話]")
RESOLUTION_PATTERN = re.compile(r"(?i)(?<!\d)((?:2160|1080|720|480)p)(?!\d)|\b([48]k)\b")
SOURCE_QUALITY_PATTERN = re.compile(
    r"(?ix)\b("
    r"blu[\s._-]?ray|bluray|bdrip|bdremux|remux|webrip|web[\s._-]?dl|hdtv|"
    r"hdrip|dvdrip|dvd|uhd|fhd"
    r")\b"
)
WEBSITE_PATTERN = re.compile(
    r"(?ix)"
    r"(?:\b(?:www\.)?[a-z0-9-]+(?:\.(?:com|net|org|cn|cc|tv|me|io|co|vip|xyz|top)){1,3}\b[^\s]*)"
)
TAIL_NOISE_PATTERN = re.compile(
    r"""(?ix)
    (?:
        (?:bd|hd|web|dvd)?(?:2160|1080|720|480)p
        | \b[48]k\b
        | \b(?:blu[\s._-]?ray|bluray|bdrip|bdremux|remux|webrip|web[\s._-]?dl|hdtv|hdrip|dvdrip|uhd|fhd)\b
        | \b(?:hdr10\+?|hdr|sdr|dv|dolby[\s._-]?vision)\b
        | \b(?:x26[45]|h[\s._-]?26[45]|hevc|avc|av1|10bit|8bit|hi10p)\b
        | \b(?:aac|ac3|eac3|ddp?|dts(?:[\s._-]?hd)?|truehd|atmos|flac|opus|mp3)\b
        | \b(?:chs|cht|chd|eng|jpn|kor|subbed|dubbed|proper|repack|limited|internal)\b
        | \b(?:yts|yify|rarbg|ettv|eztv|tgx|tigole|qxr|fgt|wiki|cmct|mteam|hdsky|hds|frds|ourtv|ntb|flux|cakes|ion10|rartv)\b
        | 中[英日韩]?字幕|字幕|中字|双语|国粤|粤国|国语|粤语|日语|韩语|英字|简繁|繁中|简中
    )
    """
)
TOKEN_NOISE = {
    "aac",
    "ac3",
    "atmos",
    "av1",
    "avc",
    "bdrip",
    "bdremux",
    "bluray",
    "chd",
    "chs",
    "cht",
    "cmct",
    "dts",
    "eac3",
    "eng",
    "ettv",
    "eztv",
    "fgt",
    "flac",
    "flux",
    "frds",
    "h264",
    "h265",
    "hdsky",
    "hevc",
    "hi10p",
    "ion10",
    "jpn",
    "kor",
    "mp3",
    "mteam",
    "ntb",
    "opus",
    "proper",
    "qxr",
    "rarbg",
    "rartv",
    "repack",
    "subbed",
    "tgx",
    "tigole",
    "truehd",
    "webdl",
    "webrip",
    "wiki",
    "x264",
    "x265",
    "yify",
    "yts",
    "中英字幕",
    "中文字幕",
    "字幕",
    "中字",
    "双语",
    "国粤双语",
    "粤语",
    "国语",
    "简中",
    "繁中",
    "简繁",
}
GENERIC_DIRECTORY_TITLES = {
    "download",
    "downloads",
    "media",
    "movie",
    "movies",
    "season",
    "series",
    "tv",
    "video",
    "videos",
    "电影",
    "影片",
    "电视剧",
    "剧集",
}


@dataclass(frozen=True)
class _TitleCandidate:
    source: str
    raw: str
    title: str
    year: Optional[int]
    quality: Optional[str]
    season: Optional[int]
    episode: Optional[int]


class MetadataService:
    def __init__(self) -> None:
        self.poster_dir = MEDIA_CACHE_DIR / "posters"
        self.backdrop_dir = MEDIA_CACHE_DIR / "backdrops"

    def enrich(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        cleaned = self._clean_parsed_metadata(media_path, parsed)
        metadata = self._local_metadata(media_path, cleaned)
        tmdb = self._tmdb_metadata(cleaned, metadata["media_type"])
        if tmdb:
            metadata.update(tmdb)
        return metadata

    def local_metadata(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        cleaned = self._clean_parsed_metadata(media_path, parsed)
        return self._local_metadata(media_path, cleaned)

    def _clean_parsed_metadata(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        candidates = self._title_candidates(media_path, parsed)
        best = max(candidates, key=self._candidate_score) if candidates else None
        stem = next((candidate for candidate in candidates if candidate.source == "stem"), None)

        cleaned = dict(parsed)
        title = best.title if best else self._fallback_title(media_path, parsed)
        year = (
            self._coerce_year(parsed.get("year"))
            or (best.year if best else None)
            or (stem.year if stem else None)
            or self._first_candidate_value(candidates, "year")
        )
        quality = (
            self._normalize_quality(parsed.get("quality"))
            or (stem.quality if stem else None)
            or (best.quality if best else None)
            or self._first_candidate_value(candidates, "quality")
        )
        season = self._coerce_int(parsed.get("season")) or (stem.season if stem else None)
        episode = self._coerce_int(parsed.get("episode")) or (stem.episode if stem else None)

        cleaned.update(
            {
                "display_title": title,
                "year": year,
                "season": season,
                "episode": episode,
                "quality": quality,
            }
        )
        return cleaned

    def _title_candidates(self, media_path: Path, parsed: dict[str, Any]) -> list[_TitleCandidate]:
        candidates: list[_TitleCandidate] = []
        parsed_title = parsed.get("display_title")
        if parsed_title:
            candidates.append(self._clean_title_candidate("parsed", str(parsed_title)))

        stem = self._clean_title_candidate("stem", media_path.stem)
        if stem.title:
            candidates.append(stem)

        parent = self._clean_title_candidate("parent", media_path.parent.name)
        if parent.title and self._is_usable_parent_candidate(parent, stem):
            candidates.append(parent)

        if self._is_season_directory(media_path.parent.name):
            grandparent = self._clean_title_candidate("grandparent", media_path.parent.parent.name)
            if grandparent.title and not self._is_generic_title(grandparent.title):
                candidates.append(grandparent)

        return [candidate for candidate in candidates if candidate.title]

    def _clean_title_candidate(self, source: str, raw: str) -> _TitleCandidate:
        text = self._normalize_raw_name(raw)
        years = self._extract_years(text)
        season, episode = self._extract_episode(text)
        quality = self._extract_quality(text)

        working = EPISODE_PATTERN.sub(" ", text)
        working = CHINESE_EPISODE_PATTERN.sub(" ", working)
        for year in years:
            working = re.sub(rf"(?<!\d){year}(?!\d)", " ", working)
        working = self._trim_at_release_noise(working)
        working = TAIL_NOISE_PATTERN.sub(" ", working)
        title = self._title_from_cleaned_text(working)

        return _TitleCandidate(
            source=source,
            raw=raw,
            title=title,
            year=years[0] if years else None,
            quality=quality,
            season=season,
            episode=episode,
        )

    def _local_metadata(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        title = parsed.get("display_title") or media_path.stem
        media_type = "tv" if parsed.get("season") and parsed.get("episode") else "movie"
        year = parsed.get("year")
        quality = parsed.get("quality")
        poster_path = self._poster_path_from_artwork_url(parsed.get("artwork_url"))
        artwork_url = parsed.get("artwork_url")
        if not poster_path:
            poster_path = self._generated_poster(media_path, title, year, quality, media_type)
            artwork_url = f"/media/artwork?path={poster_path}"
        return {
            "title": title,
            "display_title": title,
            "overview": self._generated_overview(title, year, parsed, media_type),
            "poster_path": str(poster_path),
            "artwork_url": artwork_url,
            "backdrop_url": None,
            "tmdb_id": None,
            "year": year,
            "season": parsed.get("season"),
            "episode": parsed.get("episode"),
            "quality": quality,
            "media_type": media_type,
            "metadata_source": "local",
            "metadata_updated_at": utc_now(),
        }

    def _fallback_title(self, media_path: Path, parsed: dict[str, Any]) -> str:
        title = str(parsed.get("display_title") or "").strip()
        return title or media_path.stem

    def _first_candidate_value(self, candidates: list[_TitleCandidate], attr: str) -> Any:
        for candidate in candidates:
            value = getattr(candidate, attr)
            if value:
                return value
        return None

    def _candidate_score(self, candidate: _TitleCandidate) -> tuple[int, int, int]:
        source_score = {"parent": 5, "grandparent": 4, "stem": 3, "parsed": 2}.get(candidate.source, 0)
        cjk_score = 3 if self._has_cjk(candidate.title) else 0
        year_score = 1 if candidate.year else 0
        quality_score = 1 if candidate.quality else 0
        generic_penalty = 20 if self._is_generic_title(candidate.title) else 0
        dirty_penalty = 3 if TAIL_NOISE_PATTERN.search(candidate.title) else 0
        compact_length = min(len(self._compact_title(candidate.title)), 30)
        title_score = source_score + cjk_score + year_score + quality_score - generic_penalty - dirty_penalty
        return (title_score, compact_length, -len(candidate.raw))

    def _normalize_raw_name(self, raw: str) -> str:
        text = raw.strip()
        text = re.sub(
            r"(?i)\.(?:3gp|avi|flv|m2ts|m4v|mkv|mov|mp4|mpeg|mpg|mts|rmvb|ts|webm|wmv)$",
            "",
            text,
        )
        text = WEBSITE_PATTERN.sub(" ", text)
        text = re.sub(r"(?i)\b(?:dy2018|ygdy8|zimuku|btbtt|rarbg|yts)\b", " ", text)
        return text

    def _extract_years(self, text: str) -> list[int]:
        years: list[int] = []
        for match in YEAR_PATTERN.finditer(text):
            year = int(match.group(1))
            if 1888 <= year <= MAX_RELEASE_YEAR and year not in years:
                years.append(year)
        return years

    def _extract_episode(self, text: str) -> tuple[Optional[int], Optional[int]]:
        episode_match = EPISODE_PATTERN.search(text)
        if episode_match:
            return int(episode_match.group(1)), int(episode_match.group(2))
        chinese_match = CHINESE_EPISODE_PATTERN.search(text)
        if chinese_match:
            return int(chinese_match.group(1)), int(chinese_match.group(2))
        return None, None

    def _extract_quality(self, text: str) -> Optional[str]:
        resolution = RESOLUTION_PATTERN.search(text)
        if resolution:
            return self._normalize_quality(resolution.group(1) or resolution.group(2))
        source = SOURCE_QUALITY_PATTERN.search(text)
        if source:
            return self._normalize_quality(source.group(1))
        return None

    def _normalize_quality(self, value: Any) -> Optional[str]:
        if not value:
            return None
        quality = re.sub(r"[\s._]+", "-", str(value).strip().upper())
        aliases = {
            "4K": "4K",
            "8K": "8K",
            "480P": "480P",
            "720P": "720P",
            "1080P": "1080P",
            "2160P": "2160P",
            "BDRIP": "BDRIP",
            "BDREMUX": "REMUX",
            "BLU-RAY": "BLURAY",
            "BLURAY": "BLURAY",
            "DOLBY-VISION": "DV",
            "DV": "DV",
            "DVDRIP": "DVDRIP",
            "FHD": "FHD",
            "HDTV": "HDTV",
            "REMUX": "REMUX",
            "UHD": "UHD",
            "WEB-DL": "WEB-DL",
            "WEBDL": "WEB-DL",
            "WEBRIP": "WEBRIP",
        }
        return aliases.get(quality, quality)

    def _coerce_year(self, value: Any) -> Optional[int]:
        try:
            year = int(value)
        except (TypeError, ValueError):
            return None
        return year if 1888 <= year <= MAX_RELEASE_YEAR else None

    def _coerce_int(self, value: Any) -> Optional[int]:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _trim_at_release_noise(self, text: str) -> str:
        for match in TAIL_NOISE_PATTERN.finditer(text):
            prefix = text[: match.start()]
            if self._has_title_signal(prefix):
                return prefix
        return text

    def _title_from_cleaned_text(self, text: str) -> str:
        text = WEBSITE_PATTERN.sub(" ", text)
        text = re.sub(r"[【】《》「」『』“”\"‘’\[\](){}（）<>]", " ", text)
        text = re.sub(r"[._+,/\\|:;]+", " ", text)
        text = re.sub(r"-+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        tokens: list[str] = []
        for token in text.split(" "):
            cleaned = token.strip(" \t\r\n!！?？~·`'.,")
            normalized = self._normalize_token(cleaned)
            if not normalized or self._is_noise_token(normalized, cleaned):
                continue
            tokens.append(cleaned)

        title = " ".join(tokens)
        title = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", title)
        title = re.sub(r"\s+", " ", title).strip(" -_.")
        return self._polish_title(title)

    def _is_noise_token(self, normalized: str, token: str) -> bool:
        if normalized in TOKEN_NOISE:
            return True
        return bool(RESOLUTION_PATTERN.fullmatch(token) or SOURCE_QUALITY_PATTERN.fullmatch(token))

    def _polish_title(self, title: str) -> str:
        if not title or self._has_cjk(title):
            return title
        letters = "".join(char for char in title if char.isalpha())
        if letters and (letters.islower() or letters.isupper()):
            return title.title()
        return title

    def _is_usable_parent_candidate(self, parent: _TitleCandidate, stem: _TitleCandidate) -> bool:
        if self._is_generic_title(parent.title):
            return False
        if self._has_cjk(parent.title):
            return True
        return self._titles_overlap(parent.title, stem.title)

    def _is_season_directory(self, name: str) -> bool:
        normalized = self._normalize_raw_name(name)
        normalized = re.sub(r"[._\-]+", " ", normalized).strip().lower()
        return bool(
            re.fullmatch(r"(?:season|series|s)\s*\d{1,2}", normalized)
            or re.fullmatch(r"第\s*\d{1,2}\s*季", normalized)
        )

    def _is_generic_title(self, title: str) -> bool:
        normalized = re.sub(r"\s+", " ", title.strip().lower())
        if normalized in GENERIC_DIRECTORY_TITLES:
            return True
        return bool(
            re.fullmatch(r"(?:season|series|s)\s*\d{1,2}", normalized)
            or re.fullmatch(r"第\s*\d{1,2}\s*季", normalized)
        )

    def _titles_overlap(self, left: str, right: str) -> bool:
        left_compact = self._compact_title(left)
        right_compact = self._compact_title(right)
        if not left_compact or not right_compact:
            return False
        if left_compact == right_compact:
            return True
        if min(len(left_compact), len(right_compact)) >= 4 and (
            left_compact in right_compact or right_compact in left_compact
        ):
            return True
        left_tokens = self._meaningful_ascii_tokens(left)
        right_tokens = self._meaningful_ascii_tokens(right)
        shared_tokens = left_tokens.intersection(right_tokens)
        return bool(
            shared_tokens
            and len(shared_tokens) >= 2
            and len(shared_tokens) >= min(len(left_tokens), len(right_tokens))
        )

    def _meaningful_ascii_tokens(self, title: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", title.lower()) if len(token) > 2}

    def _compact_title(self, title: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", title).lower()

    def _normalize_token(self, token: str) -> str:
        return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", token).lower()

    def _has_cjk(self, text: str) -> bool:
        return any("\u4e00" <= char <= "\u9fff" for char in text)

    def _has_title_signal(self, text: str) -> bool:
        return bool(re.search(r"[A-Za-z\u4e00-\u9fff]", text))

    def _generated_overview(
        self,
        title: str,
        year: Optional[int],
        parsed: dict[str, Any],
        media_type: str,
    ) -> str:
        kind = "剧集" if media_type == "tv" else "电影"
        parts = [f"StillFrame 从本地文件识别为{kind}《{title}》"]
        if year:
            parts.append(f"{year} 年")
        if media_type == "tv" and parsed.get("season") and parsed.get("episode"):
            parts.append(f"S{int(parsed['season']):02d}E{int(parsed['episode']):02d}")
        if parsed.get("quality"):
            parts.append(f"文件版本 {parsed['quality']}")
        return "，".join(parts) + "。连接 TMDb 后可补全真实剧情简介、海报和剧集资料。"

    def _generated_poster(
        self,
        media_path: Path,
        title: str,
        year: Optional[int],
        quality: Optional[str],
        media_type: str,
    ) -> Path:
        self.poster_dir.mkdir(parents=True, exist_ok=True)
        poster_key = "|".join(
            str(value)
            for value in (media_path, title, year, quality, media_type)
            if value
        )
        digest = hashlib.sha1(poster_key.encode("utf-8")).hexdigest()
        frame_poster = self.poster_dir / f"{digest}.jpg"
        if frame_poster.exists():
            return frame_poster
        if self._generate_frame_poster(media_path, frame_poster):
            return frame_poster

        poster = self.poster_dir / f"{digest}.svg"
        if poster.exists():
            return poster

        hue = int(digest[:2], 16) % 360
        accent = f"hsl({hue}, 58%, 58%)"
        deep = f"hsl({(hue + 34) % 360}, 38%, 15%)"
        lines = self._wrap_title(title)
        title_svg = "\n".join(
            f'<text x="48" y="{300 + index * 56}" class="title">{html.escape(line)}</text>'
            for index, line in enumerate(lines[:5])
        )
        meta = " · ".join(str(value) for value in (year, quality, media_type.upper()) if value)
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="900" viewBox="0 0 600 900">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="{accent}"/>
      <stop offset="1" stop-color="{deep}"/>
    </linearGradient>
    <style>
      .brand {{ fill: rgba(255,255,255,.68); font: 700 24px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 4px; }}
      .title {{ fill: #fff7e7; font: 800 44px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 0; }}
      .meta {{ fill: rgba(255,247,231,.76); font: 700 22px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; letter-spacing: 2px; }}
    </style>
  </defs>
  <rect width="600" height="900" fill="url(#bg)"/>
  <rect x="28" y="28" width="544" height="844" rx="22" fill="rgba(0,0,0,.16)" stroke="rgba(255,255,255,.25)" stroke-width="2"/>
  <circle cx="482" cy="146" r="78" fill="rgba(255,255,255,.16)"/>
  <circle cx="120" cy="722" r="118" fill="rgba(0,0,0,.18)"/>
  <text x="48" y="88" class="brand">STILLFRAME</text>
  {title_svg}
  <text x="48" y="812" class="meta">{html.escape(meta)}</text>
</svg>
'''
        poster.write_text(svg, encoding="utf-8")
        return poster

    def _generate_frame_poster(self, media_path: Path, target: Path) -> bool:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False

        commands = [
            self._ffmpeg_frame_command(ffmpeg, media_path, target, "00:00:10"),
            self._ffmpeg_frame_command(ffmpeg, media_path, target, "00:00:02"),
        ]
        for command in commands:
            try:
                result = subprocess.run(command, capture_output=True, timeout=20, check=False)
            except (OSError, subprocess.SubprocessError):
                continue
            if result.returncode == 0 and target.exists() and target.stat().st_size > 0:
                return True

        try:
            target.unlink(missing_ok=True)
        except OSError:
            pass
        return False

    def _ffmpeg_frame_command(self, ffmpeg: str, media_path: Path, target: Path, timestamp: str) -> list[str]:
        return [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            timestamp,
            "-i",
            str(media_path),
            "-frames:v",
            "1",
            "-vf",
            "scale=600:900:force_original_aspect_ratio=increase,crop=600:900,setsar=1",
            "-q:v",
            "3",
            "-y",
            str(target),
        ]

    def _poster_path_from_artwork_url(self, artwork_url: Optional[str]) -> Optional[Path]:
        if not artwork_url:
            return None
        path = parse_qs(urlparse(artwork_url).query).get("path", [None])[0]
        return Path(path) if path else None

    def _wrap_title(self, title: str) -> list[str]:
        if any("\u4e00" <= char <= "\u9fff" for char in title):
            return textwrap.wrap(title, width=9) or [title]
        return textwrap.wrap(title, width=16) or [title]

    def _tmdb_metadata(self, parsed: dict[str, Any], media_type: str) -> Optional[dict[str, Any]]:
        if not TMDB_API_KEY and not TMDB_BEARER_TOKEN:
            return None

        title = parsed.get("display_title")
        if not title:
            return None

        try:
            result = self._tmdb_search(title, parsed.get("year"), media_type)
            if not result:
                return None
            poster_path = self._download_tmdb_poster(result.get("poster_path"), result["id"])
        except (httpx.HTTPError, OSError, KeyError, ValueError):
            return None

        tmdb_title = result.get("title") or result.get("name") or title
        release_date = result.get("release_date") or result.get("first_air_date") or ""
        tmdb_year = int(release_date[:4]) if release_date[:4].isdigit() else parsed.get("year")
        return {
            "title": tmdb_title,
            "display_title": tmdb_title,
            "overview": result.get("overview") or None,
            "poster_path": str(poster_path) if poster_path else None,
            "artwork_url": f"/media/artwork?path={poster_path}" if poster_path else None,
            "backdrop_url": self._tmdb_image_url(result.get("backdrop_path"), "w780"),
            "tmdb_id": result.get("id"),
            "year": tmdb_year,
            "media_type": media_type,
            "metadata_source": "tmdb",
            "metadata_updated_at": utc_now(),
        }

    def _tmdb_search(self, title: str, year: Optional[int], media_type: str) -> Optional[dict[str, Any]]:
        endpoint = "search/tv" if media_type == "tv" else "search/movie"
        params: dict[str, Any] = {
            "query": title,
            "language": TMDB_LANGUAGE,
            "include_adult": "false",
        }
        if TMDB_API_KEY:
            params["api_key"] = TMDB_API_KEY
        if year:
            params["first_air_date_year" if media_type == "tv" else "year"] = year

        headers = {}
        if TMDB_BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {TMDB_BEARER_TOKEN}"

        with httpx.Client(timeout=8) as client:
            response = client.get(f"{TMDB_API_BASE}/{endpoint}", params=params, headers=headers)
            response.raise_for_status()
            results = response.json().get("results", [])
        if not results:
            return None
        return sorted(results, key=lambda item: self._tmdb_score(item, year), reverse=True)[0]

    def _tmdb_score(self, item: dict[str, Any], year: Optional[int]) -> tuple[int, float]:
        date = item.get("release_date") or item.get("first_air_date") or ""
        item_year = int(date[:4]) if date[:4].isdigit() else None
        year_score = 2 if year and item_year == year else 0
        poster_score = 1 if item.get("poster_path") else 0
        popularity = float(item.get("popularity") or 0)
        return (year_score + poster_score, popularity)

    def _download_tmdb_poster(self, poster_path: Optional[str], tmdb_id: int) -> Optional[Path]:
        if not poster_path:
            return None
        self.poster_dir.mkdir(parents=True, exist_ok=True)
        target = self.poster_dir / f"tmdb-{tmdb_id}.jpg"
        if target.exists():
            return target
        with httpx.Client(timeout=12) as client:
            response = client.get(f"{TMDB_IMAGE_BASE}/w500{poster_path}")
            response.raise_for_status()
            target.write_bytes(response.content)
        return target

    def _tmdb_image_url(self, image_path: Optional[str], size: str) -> Optional[str]:
        if not image_path:
            return None
        return f"{TMDB_IMAGE_BASE}/{size}{image_path}"
