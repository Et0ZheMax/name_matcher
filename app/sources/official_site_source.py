from __future__ import annotations

import html
import logging
import re
from typing import Dict, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class OfficialSiteSource:
    EN_PATHS = ["/en", "/eng", "/en/", "/eng/"]

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def probe(self, base_url: str) -> Optional[Dict[str, str]]:
        if not base_url:
            return None
        for url in [base_url.rstrip("/")] + [base_url.rstrip("/") + p for p in self.EN_PATHS]:
            if result := self._fetch_and_extract(url):
                return result
        return None

    def _fetch_and_extract(self, url: str) -> Optional[Dict[str, str]]:
        cache_key = f"official:{url}"
        if cached := self.cache.get("official", cache_key):
            return cached
        text = self.http.get_text(url)
        if not text:
            return None
        fields = {
            "title": _extract_first(text, r"<title[^>]*>(.*?)</title>"),
            "og:title": _extract_meta(text, "og:title"),
            "og:site_name": _extract_meta(text, "og:site_name"),
            "h1": _extract_first(text, r"<h1[^>]*>(.*?)</h1>"),
        }
        for k, value in fields.items():
            value = _clean_html(value)
            if self._looks_like_en_name(value):
                data = {
                    "candidate_text": self._cleanup(value),
                    "source_url": url,
                    "notes": f"Accepted from {k} on English-like official page",
                }
                self.cache.set("official", cache_key, data)
                return data
        return None

    @staticmethod
    def _looks_like_en_name(text: str) -> bool:
        return bool(text and len(text) > 6 and not re.search(r"[А-Яа-я]", text) and re.search(r"(University|Institute|Academy|Center|Centre|Laboratory|Federal)", text, re.I))

    @staticmethod
    def _cleanup(text: str) -> str:
        return re.sub(r"\s+[|\-–].*$", "", re.sub(r"\s+", " ", text).strip()).strip()


def _extract_meta(text: str, prop: str) -> str:
    return _extract_first(text, rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\'](.*?)["\']') or _extract_first(text, rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(prop)}["\']')


def _extract_first(text: str, pattern: str) -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return m.group(1).strip() if m else ""


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()
