from __future__ import annotations

import re
from typing import List

from app.config import ScoringConfig
from app.models import Candidate


GENERIC_TERMS = {"university", "institute", "academy", "center", "centre", "laboratory"}
STOPWORDS = {"the", "of", "for", "at", "and", "named", "after"}


def score_candidates(candidates: List[Candidate], config: ScoringConfig) -> List[Candidate]:
    if not candidates:
        return []

    for c in candidates:
        score = 0
        source_set = set(c.contributing_sources or [c.source])
        for src in source_set:
            score += config.source_weights.get(src, 0)

        if "site_title_match" in c.support_signals:
            score += config.source_weights["site_title_match"]
        if len(source_set) > 1:
            score += config.source_weights["multi_source_support"]
        if "source_conflict" in c.support_signals:
            score += config.penalties["source_conflict"]

        words = set(w.lower() for w in c.candidate_text.split())
        if words and words.issubset(GENERIC_TERMS):
            score += config.penalties["too_generic"]

        if c.source == "translit_fallback" and any(x.source != "translit_fallback" for x in candidates):
            score -= 35
        elif c.source == "translit_fallback":
            score += config.penalties["fallback_only"]

        if c.source == "wikipedia" and len(candidates) == 1:
            score += config.penalties["wikipedia_only"]

        c.score = score
        c.confidence = min(max((score + 30) / 150, 0.0), 1.0)
    return sorted(candidates, key=lambda x: x.score, reverse=True)


def apply_pubmed_boost(candidate: Candidate, config: ScoringConfig, exact_count: int, similar: bool, affiliation_match: bool = False) -> Candidate:
    if exact_count > 0:
        candidate.score += config.source_weights["pubmed_exact_positive"]
    if similar:
        candidate.score += config.source_weights["pubmed_affiliation_similar"]
    if affiliation_match:
        candidate.score += 10
    candidate.confidence = min(max((candidate.score + 30) / 150, 0.0), 1.0)
    return candidate


def status_from_score(candidate: Candidate, config: ScoringConfig) -> str:
    s = candidate.score
    t = config.thresholds
    if candidate.source == "translit_fallback" and s <= t["fallback"]:
        return "fallback"
    if s >= t["official"] and "official_site" in (candidate.contributing_sources or [candidate.source]):
        return "official"
    if s >= t["best_match"]:
        return "best_match"
    return "manual_review_needed"


def display_normalized_key(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\bsb\s+ras\b", "siberian branch russian academy sciences", text)
    text = re.sub(r"\bsiberian\s+branch\s+of\s+the?\s*russian\s+academy\s+of\s+sciences\b", "siberian branch russian academy sciences", text)
    text = re.sub(r"\binst\.?\b", "institute", text)
    text = re.sub(r"\buniv\.?\b", "university", text)
    text = re.sub(r"\bacad\.?\b", "academy", text)
    text = re.sub(r"\bfederal\s+state\s+budgetary\b", "federal", text)
    text = re.sub(r"\bstate\s+budgetary\b", "", text)
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    tokens = [tok for tok in re.sub(r"\s+", " ", text).strip().split() if tok and tok not in STOPWORDS]
    return " ".join(tokens)


def canonical_match_key(text: str) -> str:
    display = display_normalized_key(text)
    if not display:
        return ""
    return " ".join(sorted(display.split()))


def normalize_candidate_key(text: str) -> str:
    """Backward-compatible alias for canonical match key."""
    return canonical_match_key(text)
