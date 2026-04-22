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
        return [
            {
                "name": "Institute of Chemistry SB RAS",
                "id": "https://ror.org/abc123",
                "links": ["https://example.org"],
                "aliases": ["Institute of Chemistry, Siberian Branch, Russian Academy of Sciences"],
            }
        ]


class DummyWikidata(WikidataSource):
    def search(self, query: str):
        return {
            "en_label": "Institute of Chemistry SB RAS",
            "enwiki_title": "Institute of Chemistry SB RAS",
            "wikidata_url": "https://www.wikidata.org/wiki/Q1",
        }


class DummyWikipedia(WikipediaSource):
    def from_en_title(self, title: str):
        return {"title": title, "fullurl": "https://en.wikipedia.org/wiki/Institute_of_Chemistry_SB_RAS"}


class DummyOfficial(OfficialSiteSource):
    def probe(self, base_url: str, known_websites=None):
        return {
            "candidate_text": "Institute of Chemistry SB RAS",
            "source_url": "https://example.org/en/about",
            "notes": "Accepted from title",
            "snippet": "Institute of Chemistry SB RAS official page",
        }


class DummyPubMed(PubMedSource):
    def query_count(self, query: str, retmax: int = 5):
        return {"count": 3, "ids": ["1", "2", "3"]}

    def fetch_summaries(self, pmids):
        return ["Institute of Chemistry SB RAS published study"]

    def fetch_affiliations(self, pmids):
        return ["Institute of Chemistry SB RAS, Novosibirsk, Russia"]


def test_pipeline_smoke_no_network(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    with input_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["org"])
        w.writeheader()
        w.writerow({"org": "Институт химии СО РАН"})
        w.writerow({"org": "Институт химии СО РАН"})

    cfg = mode_to_config("balanced")
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
    runner = PipelineRunner(cfg, builder, Resolver(cfg, logger=logger), CandidateValidator(DummyPubMed(cfg, cache, logger), cfg), logger)

    result = runner.run(input_csv, org_column="org", limit=2)
    assert len(result.organizations) == 1
    assert result.organizations[0].organization_en_final == "Institute of Chemistry SB RAS"
    assert result.organizations[0].pubmed.pubmed_pmids == ["1", "2", "3"]
    assert len(result.manual_review) == 0
