from __future__ import annotations

import html
import logging
import re
from typing import Dict, List, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class OfficialSiteSource:
    EN_PATHS = ["/en", "/eng", "/international", "/about", "/contacts", "/en/about", "/en/contacts"]
    STRONG_FIELDS = ("title", "og:title", "og:site_name", "h1")
    WEAK_FIELDS = ("meta:title", "meta:description", "h2")

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def probe(self, base_url: str, known_websites: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
        urls: List[str] = []
        for url in ([base_url] + (known_websites or [])):
            if url and url.rstrip("/") not in urls:
                urls.append(url.rstrip("/"))

        for root in urls:
            for url in [root] + [root + p for p in self.EN_PATHS]:
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

        fields: Dict[str, str] = {
            "title": _extract_first(text, r"<title[^>]*>(.*?)</title>"),
            "og:title": _extract_meta(text, "og:title"),
            "og:site_name": _extract_meta(text, "og:site_name"),
            "meta:title": _extract_meta_name(text, "title"),
            "meta:description": _extract_meta_name(text, "description"),
            "h1": _extract_first(text, r"<h1[^>]*>(.*?)</h1>"),
            "h2": _extract_first(text, r"<h2[^>]*>(.*?)</h2>"),
        }

        for field_name in self.STRONG_FIELDS:
            cleaned = _clean_html(fields.get(field_name, ""))
            if self._looks_like_en_name(cleaned):
                data = {
                    "candidate_text": self._cleanup(cleaned),
                    "source_url": url,
                    "notes": f"Accepted from {field_name} on official page",
                    "snippet": _extract_relevant_snippet(text, cleaned),
                }
                self.cache.set("official", cache_key, data)
                return data

        weak_snippets = []
        for field_name in self.WEAK_FIELDS:
            cleaned = _clean_html(fields.get(field_name, ""))
            if cleaned:
                weak_snippets.append(f"{field_name}: {cleaned[:120]}")

        if weak_snippets:
            self.logger.debug("Official site weak evidence for %s: %s", url, " | ".join(weak_snippets))
        return None

    @staticmethod
    def _looks_like_en_name(text: str) -> bool:
        return bool(
            text
            and len(text) > 6
            and not re.search(r"[А-Яа-я]", text)
            and re.search(r"(University|Institute|Academy|Center|Centre|Laboratory|Federal|Research)", text, re.I)
        )

    @staticmethod
    def _cleanup(text: str) -> str:
        return re.sub(r"\s+[|\-–].*$", "", re.sub(r"\s+", " ", text).strip()).strip()


def _extract_meta(text: str, prop: str) -> str:
    return _extract_first(text, rf'<meta[^>]+property=["\']{re.escape(prop)}["\'][^>]+content=["\'](.*?)["\']') or _extract_first(text, rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(prop)}["\']')


def _extract_meta_name(text: str, name: str) -> str:
    return _extract_first(text, rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']') or _extract_first(text, rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(name)}["\']')


def _extract_first(text: str, pattern: str) -> str:
    m = re.search(pattern, text, flags=re.I | re.S)
    return m.group(1).strip() if m else ""


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


def _extract_relevant_snippet(page_text: str, candidate_text: str) -> str:
    plain = _clean_html(page_text)
    tokens = [t for t in re.findall(r"[a-zA-Z]{4,}", candidate_text.lower())[:3] if t]
    if not tokens:
        return plain[:200]
    for token in tokens:
        idx = plain.lower().find(token)
        if idx >= 0:
            start = max(0, idx - 80)
            end = min(len(plain), idx + 160)
            return plain[start:end]
    return plain[:200]
