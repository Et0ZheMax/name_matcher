import csv
from pathlib import Path

from app.cache import JsonCache
from app.config import mode_to_config
from app.logging_utils import setup_logging
from app.pipeline.candidate_builder import CandidateBuilder
from app.pipeline.resolver import Resolver
from app.pipeline.runner import PipelineRunner
from app.pipeline.validator import CandidateValidator
from app.sources import OfficialSiteSource, PubMedSource, RORSource, TranslitFallbackSource, WikidataSource, WikipediaSource


class DummyROR(RORSource):
    def search(self, query: str, limit: int = 5):
        return [{"name": "Tomsk State University", "id": "https://ror.org/x", "links": ["https://example.org"], "aliases": []}]


class DummyWikidata(WikidataSource):
    def search(self, query: str):
        return {"en_label": "Tomsk State University", "enwiki_title": "Tomsk State University", "wikidata_url": "https://wikidata.org/Q1"}


class DummyWikipedia(WikipediaSource):
    def from_en_title(self, title: str):
        return {"title": title, "fullurl": "https://en.wikipedia.org/wiki/Tomsk_State_University"}


class DummyOfficial(OfficialSiteSource):
    def probe(self, base_url: str, known_websites=None):
        return {"candidate_text": "Tomsk State University", "source_url": "https://example.org/en", "notes": "title", "snippet": "Tomsk State University"}


class DummyPubMed(PubMedSource):
    def query_count(self, query: str, retmax: int = 5):
        return {"count": 0, "ids": []}

    def fetch_summaries(self, pmids):
        return []

    def fetch_affiliations(self, pmids):
        return []


def _build_runner(tmp_path: Path, threshold: float) -> PipelineRunner:
    cfg = mode_to_config("balanced")
    cfg.manual_review_confidence_threshold = threshold
    logger = setup_logging(tmp_path / "logs", debug=False)
    cache = JsonCache(tmp_path / ".cache", enabled=False)

    builder = CandidateBuilder(
        DummyROR(cfg, cache, logger),
        DummyOfficial(cfg, cache, logger),
        DummyWikidata(cfg, cache, logger),
        DummyWikipedia(cfg, cache, logger),
        TranslitFallbackSource(),
        logger,
    )
    return PipelineRunner(cfg, builder, Resolver(cfg, logger=logger), CandidateValidator(DummyPubMed(cfg, cache, logger), cfg), logger)


def test_manual_review_threshold_from_config(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    with input_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["org"])
        w.writeheader()
        w.writerow({"org": "Томский государственный университет"})

    strict_runner = _build_runner(tmp_path / "strict", threshold=1.01)
    strict_result = strict_runner.run(input_csv, org_column="org")
    assert len(strict_result.manual_review) == 1

    lenient_runner = _build_runner(tmp_path / "lenient", threshold=0.1)
    lenient_result = lenient_runner.run(input_csv, org_column="org")
    assert len(lenient_result.manual_review) == 0
