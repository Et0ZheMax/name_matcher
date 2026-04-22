from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class WikidataSource:
    endpoint = "https://www.wikidata.org/w/api.php"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def search(self, query: str) -> Optional[Dict[str, Any]]:
        cache_key = f"wikidata:{query}"
        if cached := self.cache.get("wikidata", cache_key):
            return cached
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "ru",
            "format": "json",
            "type": "item",
            "limit": 1,
        }
        payload = self.http.get_json(self.endpoint, params=params) or {}
        results = payload.get("search", [])
        if not results:
            return None
        entity_id = results[0].get("id")
        if not entity_id:
            return None
        entity = self.get_entity(entity_id)
        if entity:
            self.cache.set("wikidata", cache_key, entity)
        return entity

    def get_entity(self, entity_id: str) -> Optional[Dict[str, Any]]:
        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "languages": "en|ru",
            "props": "labels|sitelinks|claims",
            "format": "json",
        }
        payload = self.http.get_json(self.endpoint, params=params) or {}
        ent = payload.get("entities", {}).get(entity_id, {})
        if not ent:
            return None
        sitelinks = ent.get("sitelinks", {})
        return {
            "entity_id": entity_id,
            "en_label": ent.get("labels", {}).get("en", {}).get("value", ""),
            "ru_label": ent.get("labels", {}).get("ru", {}).get("value", ""),
            "enwiki_title": sitelinks.get("enwiki", {}).get("title"),
            "ruwiki_title": sitelinks.get("ruwiki", {}).get("title"),
            "wikidata_url": f"https://www.wikidata.org/wiki/{entity_id}",
        }
