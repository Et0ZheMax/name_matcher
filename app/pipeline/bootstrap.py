from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from app.cache import JsonCache
from app.config import AppConfig, mode_to_config
from app.logging_utils import setup_logging
from app.pipeline.candidate_builder import CandidateBuilder
from app.pipeline.resolver import Resolver
from app.pipeline.runner import PipelineRunner
from app.pipeline.validator import CandidateValidator
from app.sources import OfficialSiteSource, PubMedSource, RORSource, TranslitFallbackSource, WikidataSource, WikipediaSource


@dataclass(slots=True)
class PipelineRuntime:
    config: AppConfig
    runner: PipelineRunner


def build_runtime(
    mode: str,
    no_cache: bool,
    debug: bool,
    log_callback: Optional[Callable[..., None]] = None,
) -> PipelineRuntime:
    config = mode_to_config(mode)
    logger = setup_logging(config.logs_dir, debug=debug, callback=log_callback)
    cache = JsonCache(config.cache_dir, ttl_hours=config.cache_ttl_hours, enabled=not no_cache)

    ror = RORSource(config, cache, logger)
    official = OfficialSiteSource(config, cache, logger)
    wikidata = WikidataSource(config, cache, logger)
    wikipedia = WikipediaSource(config, cache, logger)
    translit = TranslitFallbackSource()
    pubmed = PubMedSource(config, cache, logger)

    builder = CandidateBuilder(ror, official, wikidata, wikipedia, translit, logger)
    resolver = Resolver(config, logger=logger)
    validator = CandidateValidator(pubmed, config)

    runner = PipelineRunner(config, builder, resolver, validator, logger)
    return PipelineRuntime(config=config, runner=runner)
