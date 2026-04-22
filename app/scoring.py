from __future__ import annotations

from collections import Counter
from typing import Iterable, List

from app.config import ScoringConfig
from app.models import Candidate


GENERIC_TERMS = {"university", "institute", "academy", "center", "centre", "laboratory"}


def score_candidates(candidates: List[Candidate], config: ScoringConfig) -> List[Candidate]:
    support_counts = Counter(_norm(c.candidate_text) for c in candidates)

    for c in candidates:
        score = 0
        score += config.source_weights.get(c.source, 0)
        if "site_title_match" in c.support_signals:
            score += config.source_weights["site_title_match"]
        if support_counts[_norm(c.candidate_text)] > 1:
            score += config.source_weights["multi_source_support"]

        words = set(w.lower() for w in c.candidate_text.split())
        if words and words.issubset(GENERIC_TERMS):
            score += config.penalties["too_generic"]
        if c.source == "translit_fallback" and len(candidates) == 1:
            score += config.penalties["fallback_only"]
        if c.source == "wikipedia" and len(candidates) == 1:
            score += config.penalties["wikipedia_only"]

        c.score = score
        c.confidence = min(max((score + 30) / 130, 0.0), 1.0)
    return sorted(candidates, key=lambda x: x.score, reverse=True)


def apply_pubmed_boost(candidate: Candidate, config: ScoringConfig, exact_count: int, similar: bool) -> Candidate:
    if exact_count > 0:
        candidate.score += config.source_weights["pubmed_exact_positive"]
    if similar:
        candidate.score += config.source_weights["pubmed_affiliation_similar"]
    candidate.confidence = min(max((candidate.score + 30) / 130, 0.0), 1.0)
    return candidate


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def status_from_score(candidate: Candidate, config: ScoringConfig) -> str:
    s = candidate.score
    t = config.thresholds
    if candidate.source == "translit_fallback" and s <= t["fallback"]:
        return "fallback"
    if s >= t["official"] and candidate.source == "official_site":
        return "official"
    if s >= t["best_match"]:
        return "best_match"
    return "manual_review_needed"
