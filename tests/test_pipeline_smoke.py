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


class DummyPubMed(PubMedSource):
    def query_count(self, query: str):
        return {"count": 0, "ids": []}

    def fetch_summaries(self, pmids):
        return []


def test_pipeline_smoke_no_network(tmp_path: Path) -> None:
    input_csv = tmp_path / "input.csv"
    with input_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["org"])
        w.writeheader()
        w.writerow({"org": "Институт химии"})
        w.writerow({"org": "Институт химии"})

    cfg = mode_to_config("balanced")
    logger = setup_logging(tmp_path / "logs", debug=False)
    cache = JsonCache(tmp_path / ".cache", enabled=False)

    builder = CandidateBuilder(
        RORSource(cfg, cache, logger),
        OfficialSiteSource(cfg, cache, logger),
        WikidataSource(cfg, cache, logger),
        WikipediaSource(cfg, cache, logger),
        TranslitFallbackSource(),
        logger,
    )
    runner = PipelineRunner(cfg, builder, Resolver(cfg), CandidateValidator(DummyPubMed(cfg, cache, logger), cfg), logger)

    result = runner.run(input_csv, org_column="org", limit=2)
    assert len(result.organizations) == 1
    assert result.organizations[0].organization_en_final
