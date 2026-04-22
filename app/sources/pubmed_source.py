from __future__ import annotations

import logging
from typing import Dict, List

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class PubMedSource:
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def query_count(self, query: str) -> Dict[str, object]:
        cache_key = f"pubmed_count:{query}"
        if cached := self.cache.get("pubmed", cache_key):
            return cached
        payload = self.http.get_json(self.esearch_url, params={"db": "pubmed", "retmode": "json", "term": query, "retmax": 5}) or {}
        result = payload.get("esearchresult", {})
        data = {"count": int(result.get("count", 0) or 0), "ids": result.get("idlist", [])}
        self.cache.set("pubmed", cache_key, data)
        return data

    def fetch_summaries(self, pmids: List[str]) -> List[str]:
        if not pmids:
            return []
        cache_key = f"pubmed_summary:{','.join(pmids)}"
        if cached := self.cache.get("pubmed", cache_key):
            return cached
        payload = self.http.get_json(self.esummary_url, params={"db": "pubmed", "retmode": "json", "id": ",".join(pmids[:5])}) or {}
        result = payload.get("result", {})
        texts = [result.get(pmid, {}).get("title", "") for pmid in pmids[:5] if pmid in result]
        self.cache.set("pubmed", cache_key, texts)
        return texts
