from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class RORSource:
    base_url = "https://api.ror.org/organizations"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        cache_key = f"ror:{query}"
        if cached := self.cache.get("ror", cache_key):
            self.logger.debug("ROR cache hit for %s", query)
            return cached

        data = self.http.get_json(self.base_url, params={"query": query}) or {}
        item = data.get("items", [{}])[0] if data.get("items") else None
        if item:
            self.cache.set("ror", cache_key, item)
        return item
