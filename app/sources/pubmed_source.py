from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Dict, List

from app.cache import JsonCache
from app.config import AppConfig
from app.sources.http_client import HttpClient


class PubMedSource:
    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    efetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def __init__(self, config: AppConfig, cache: JsonCache, logger: logging.Logger) -> None:
        self.cache = cache
        self.logger = logger
        self.http = HttpClient(config)

    def query_count(self, query: str, retmax: int = 5) -> Dict[str, object]:
        cache_key = f"pubmed_count:{query}:{retmax}"
        if cached := self.cache.get("pubmed", cache_key):
            return cached
        payload = self.http.get_json(self.esearch_url, params={"db": "pubmed", "retmode": "json", "term": query, "retmax": retmax}) or {}
        result = payload.get("esearchresult", {})
        data = {"count": int(result.get("count", 0) or 0), "ids": result.get("idlist", [])[:retmax]}
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

    def fetch_affiliations(self, pmids: List[str]) -> List[str]:
        if not pmids:
            return []
        ids = ",".join(pmids[:5])
        cache_key = f"pubmed_affiliation:{ids}"
        if cached := self.cache.get("pubmed", cache_key):
            return cached

        xml_text = self.http.get_text(self.efetch_url, params={"db": "pubmed", "id": ids, "retmode": "xml"}) or ""
        affiliations = self._extract_affiliations(xml_text)
        self.cache.set("pubmed", cache_key, affiliations)
        return affiliations

    @staticmethod
    def _extract_affiliations(xml_text: str) -> List[str]:
        if not xml_text:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        result: List[str] = []
        for node in root.findall(".//Affiliation"):
            if node.text and node.text.strip():
                result.append(" ".join(node.text.split()))
        return result
