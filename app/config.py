from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict


@dataclass(slots=True)
class ScoringConfig:
    source_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "official_site": 50,
            "ror": 25,
            "wikidata": 20,
            "wikipedia": 10,
            "site_title_match": 20,
            "pubmed_exact_positive": 15,
            "pubmed_affiliation_similar": 20,
            "multi_source_support": 20,
        }
    )
    penalties: Dict[str, int] = field(
        default_factory=lambda: {
            "fallback_only": -25,
            "wikipedia_only": -10,
            "too_generic": -20,
            "source_conflict": -20,
            "pubmed_other_org": -30,
        }
    )
    thresholds: Dict[str, int] = field(
        default_factory=lambda: {
            "official": 85,
            "best_match": 55,
            "fallback": 20,
            "manual_review": 0,
        }
    )


@dataclass(slots=True)
class AppConfig:
    cache_dir: Path = Path(".cache")
    cache_ttl_hours: int = 24 * 14
    logs_dir: Path = Path("logs")
    outputs_dir: Path = Path("outputs")
    request_timeout_sec: int = 15
    max_retries: int = 3
    retry_backoff_sec: float = 1.5
    user_agent: str = "org-name-enricher/0.1 (+https://example.local)"
    mode: str = "balanced"
    scoring: ScoringConfig = field(default_factory=ScoringConfig)


def mode_to_config(mode: str) -> AppConfig:
    cfg = AppConfig(mode=mode)
    if mode == "strict":
        cfg.scoring.thresholds["official"] = 95
        cfg.scoring.thresholds["best_match"] = 70
    elif mode == "aggressive":
        cfg.scoring.thresholds["official"] = 75
        cfg.scoring.thresholds["best_match"] = 45
    return cfg
