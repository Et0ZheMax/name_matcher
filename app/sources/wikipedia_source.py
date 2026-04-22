from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class WikipediaSource:
    endpoint = "https://en.wikipedia.org/w/api.php"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def from_en_title(self, title: str) -> Optional[Dict[str, Any]]:
        cache_key = f"wikipedia:{title}"
        if cached := self.cache.get("wikipedia", cache_key):
            return cached
        params = {"action": "query", "prop": "info", "inprop": "url", "titles": title, "format": "json"}
        payload = self.http.get_json(self.endpoint, params=params) or {}
        pages = payload.get("query", {}).get("pages", {})
        page = next(iter(pages.values())) if pages else {}
        if not page:
            return None
        data = {"title": page.get("title", title), "fullurl": page.get("fullurl", "")}
        self.cache.set("wikipedia", cache_key, data)
        return data
