from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class RORSource:
    base_url = "https://api.ror.org/organizations"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        cache_key = f"ror:{query}:{limit}"
        if cached := self.cache.get("ror", cache_key):
            self.logger.debug("ROR cache hit for %s", query)
            return cached

        data = self.http.get_json(self.base_url, params={"query": query}) or {}
        items = data.get("items") or []
        ranked = sorted(items, key=lambda x: self._local_rank(query, x), reverse=True)[:limit]
        if ranked:
            self.cache.set("ror", cache_key, ranked)
        return ranked

    def _local_rank(self, query: str, item: Dict[str, Any]) -> float:
        q = _norm(query)
        label = _norm(item.get("name", ""))
        aliases = [_norm(a) for a in item.get("aliases", []) if a]

        base = SequenceMatcher(None, q, label).ratio()
        alias_similarity = max((SequenceMatcher(None, q, a).ratio() for a in aliases), default=0.0)
        alias_overlap_bonus = 0.08 if any(q in a or a in q for a in aliases) else 0.0
        has_website_bonus = 0.02 if item.get("links") else 0.0
        return max(base, alias_similarity) + alias_overlap_bonus + has_website_bonus


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()
