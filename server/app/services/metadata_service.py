from __future__ import annotations

import hashlib
import html
import textwrap
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import MEDIA_CACHE_DIR, TMDB_API_KEY, TMDB_BEARER_TOKEN, TMDB_LANGUAGE
from app.services.library_service import utc_now


TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"


class MetadataService:
    def __init__(self) -> None:
        self.poster_dir = MEDIA_CACHE_DIR / "posters"
        self.backdrop_dir = MEDIA_CACHE_DIR / "backdrops"

    def enrich(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        metadata = self._local_metadata(media_path, parsed)
        tmdb = self._tmdb_metadata(parsed, metadata["media_type"])
        if tmdb:
            metadata.update(tmdb)
        return metadata

    def _local_metadata(self, media_path: Path, parsed: dict[str, Any]) -> dict[str, Any]:
        title = parsed.get("display_title") or media_path.stem
        media_type = "tv" if parsed.get("season") and parsed.get("episode") else "movie"
        year = parsed.get("year")
        poster_path = self._poster_path_from_artwork_url(parsed.get("artwork_url"))
        artwork_url = parsed.get("artwork_url")
        if not poster_path:
            poster_path = self._generated_poster(media_path, title, year, parsed.get("quality"), media_type)
            artwork_url = f"/media/artwork?path={poster_path}"
        return {
            "title": title,
            "display_title": title,
            "overview": self._generated_overview(title, year, parsed, media_type),
            "poster_path": str(poster_path),
            "artwork_url": artwork_url,
            "backdrop_url": None,
            "tmdb_id": None,
            "media_type": media_type,
            "metadata_source": "local",
            "metadata_updated_at": utc_now(),
        }

    def _generated_overview(
        self,
        title: str,
        year: Optional[int],
        parsed: dict[str, Any],
        media_type: str,
    ) -> str:
        parts = [f"StillFrame 根据本地文件名识别出《{title}》"]
        if year:
            parts.append(f"年份 {year}")
        if media_type == "tv" and parsed.get("season") and parsed.get("episode"):
            parts.append(f"第 {parsed['season']} 季第 {parsed['episode']} 集")
        if parsed.get("quality"):
            parts.append(f"画质标记 {parsed['quality']}")
        return "，".join(parts) + "。配置 TMDb 后可自动补全真实剧情简介、海报和剧集资料。"

    def _generated_poster(
        self,
        media_path: Path,
        title: str,
        year: Optional[int],
        quality: Optional[str],
        media_type: str,
    ) -> Path:
        self.poster_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(str(media_path).encode("utf-8")).hexdigest()
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
