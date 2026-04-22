from __future__ import annotations

import argparse
from pathlib import Path

from app.cache import JsonCache
from app.config import mode_to_config
from app.exporter import export_result
from app.logging_utils import setup_logging
from app.pipeline.candidate_builder import CandidateBuilder
from app.pipeline.resolver import Resolver
from app.pipeline.runner import PipelineRunner
from app.pipeline.validator import CandidateValidator
from app.sources import OfficialSiteSource, PubMedSource, RORSource, TranslitFallbackSource, WikidataSource, WikipediaSource


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Enrich RU organization names with EN candidates + PubMed validation")
    p.add_argument("input_file", type=Path)
    p.add_argument("--output", type=Path, default=Path("outputs/result.xlsx"))
    p.add_argument("--org-column", type=str, default=None)
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--mode", choices=["strict", "balanced", "aggressive"], default="balanced")
    p.add_argument("--first-column-as-org", action="store_true")
    return p


def main() -> None:
    args = build_parser().parse_args()
    config = mode_to_config(args.mode)

    logger = setup_logging(config.logs_dir, debug=args.debug)
    cache = JsonCache(config.cache_dir, ttl_hours=config.cache_ttl_hours, enabled=not args.no_cache)

    ror = RORSource(config, cache, logger)
    official = OfficialSiteSource(config, cache, logger)
    wikidata = WikidataSource(config, cache, logger)
    wikipedia = WikipediaSource(config, cache, logger)
    translit = TranslitFallbackSource()
    pubmed = PubMedSource(config, cache, logger)

    builder = CandidateBuilder(ror, official, wikidata, wikipedia, translit, logger)
    resolver = Resolver(config)
    validator = CandidateValidator(pubmed, config)

    runner = PipelineRunner(config, builder, resolver, validator, logger)

    # --resume prepared for future granular checkpointing; cache already helps avoid repeated network calls.
    if args.resume:
        logger.info("Resume mode enabled: using cached source responses where available.")

    result = runner.run(
        args.input_file,
        org_column=args.org_column,
        first_column_as_org=args.first_column_as_org,
        limit=args.limit,
    )
    export_result(result, args.output)
    logger.info("Done. Output written to %s", args.output)


if __name__ == "__main__":
    main()
