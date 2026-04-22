from app.config import ScoringConfig
from app.models import Candidate
from app.scoring import canonical_match_key, display_normalized_key, normalize_candidate_key, score_candidates, status_from_score


def mk(source: str, text: str, contributing_sources=None, signals=None) -> Candidate:
    return Candidate(
        "raw",
        "norm",
        text,
        source=source,
        contributing_sources=contributing_sources or [source],
        support_signals=signals or [],
    )


def test_scoring_prioritizes_official_site() -> None:
    cfg = ScoringConfig()
    candidates = [mk("official_site", "Tomsk State University"), mk("wikipedia", "Tomsk State University")]
    ranked = score_candidates(candidates, cfg)
    assert ranked[0].source == "official_site"


def test_status_for_fallback() -> None:
    cfg = ScoringConfig()
    c = mk("translit_fallback", "Institut Khimii")
    ranked = score_candidates([c], cfg)
    assert status_from_score(ranked[0], cfg) == "fallback"


def test_scoring_penalizes_source_conflict() -> None:
    cfg = ScoringConfig()
    conflicting = mk(
        "ror",
        "Example Institute",
        contributing_sources=["ror", "wikidata"],
        signals=["source_conflict"],
    )
    clean = mk("ror", "Example Institute", contributing_sources=["ror", "wikidata"])
    ranked = score_candidates([conflicting, clean], cfg)
    assert ranked[0] is clean


def test_normalize_candidate_key_handles_academic_abbrev() -> None:
    key = normalize_candidate_key("Inst. of Chemistry, SB RAS")
    assert "institute" in key
    assert "siberian" in key
    assert "academy" in key


def test_display_and_canonical_keys_are_split() -> None:
    display = display_normalized_key("University of Tomsk Inst. of Chemistry")
    canonical = canonical_match_key("University of Tomsk Inst. of Chemistry")
    assert display == "university tomsk institute chemistry"
    assert canonical == "chemistry institute tomsk university"
