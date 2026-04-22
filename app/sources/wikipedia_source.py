from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class WikipediaSource:
    en_endpoint = "https://en.wikipedia.org/w/api.php"
    ru_endpoint = "https://ru.wikipedia.org/w/api.php"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def from_en_title(self, title: str) -> Optional[Dict[str, Any]]:
        cache_key = f"wikipedia:{title}"
        if cached := self.cache.get("wikipedia", cache_key):
            return cached
        params = {"action": "query", "prop": "info", "inprop": "url", "titles": title, "format": "json"}
        payload = self.http.get_json(self.en_endpoint, params=params) or {}
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values())) if pages else {}
        if not page:
            return None
        data = {"title": page.get("title", title), "fullurl": page.get("fullurl", "")}
        self.cache.set("wikipedia", cache_key, data)
        return data

    def search_ru(self, query: str) -> Optional[Dict[str, Any]]:
        cache_key = f"ruwiki:search:{query}"
        if cached := self.cache.get("wikipedia", cache_key):
            return cached
        params = {
            "action": "query",
            "list": "search",
            "srlimit": 1,
            "srsearch": query,
            "format": "json",
        }
        payload = self.http.get_json(self.ru_endpoint, params=params) or {}
        results = payload.get("query", {}).get("search", [])
        if not results:
            return None
        title = results[0].get("title", "")
        if not title:
            return None
        page = self._ru_page_info(title)
        if page:
            self.cache.set("wikipedia", cache_key, page)
        return page

    def get_ru_international_name(self, title: str) -> str:
        if not title:
            return ""
        cache_key = f"ruwiki:infobox_international_name:{title}"
        if cached := self.cache.get("wikipedia", cache_key):
            return str(cached.get("value", ""))

        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
            "format": "json",
        }
        payload = self.http.get_json(self.ru_endpoint, params=params) or {}
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values())) if pages else {}
        revision = ((page.get("revisions") or [{}])[0]).get("slots", {}).get("main", {})
        wikitext = revision.get("*", "") or revision.get("content", "")
        value = _extract_international_name(wikitext)
        self.cache.set("wikipedia", cache_key, {"value": value})
        return value

    def _ru_page_info(self, title: str) -> Optional[Dict[str, Any]]:
        params = {"action": "query", "prop": "info", "inprop": "url", "titles": title, "format": "json"}
        payload = self.http.get_json(self.ru_endpoint, params=params) or {}
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values())) if pages else {}
        if not page:
            return None
        return {"title": page.get("title", title), "fullurl": page.get("fullurl", "")}


def _extract_international_name(wikitext: str) -> str:
    if not wikitext:
        return ""
    patterns = [
        r"\|\s*международное\s+название\s*=\s*(.+)",
        r"\|\s*international\s+name\s*=\s*(.+)",
    ]
    for pattern in patterns:
        m = re.search(pattern, wikitext, flags=re.I)
        if not m:
            continue
        value = m.group(1).split("\n", 1)[0].strip()
        cleaned = _clean_wiki_markup(value)
        if cleaned and re.search(r"[A-Za-z]", cleaned):
            return cleaned
    return ""


def _clean_wiki_markup(text: str) -> str:
    cleaned = text
    cleaned = re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", cleaned)
    cleaned = re.sub(r"\{\{[^{}]*\}\}", " ", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"''+", "", cleaned)
    cleaned = re.sub(r"&nbsp;", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ;,")
    return cleaned
