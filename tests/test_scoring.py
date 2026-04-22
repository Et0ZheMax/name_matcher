from app.config import ScoringConfig
from app.models import Candidate
from app.scoring import score_candidates, status_from_score


def mk(source: str, text: str) -> Candidate:
    return Candidate("raw", "norm", text, source=source)


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
