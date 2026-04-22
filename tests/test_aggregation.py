import logging

from app.models import Candidate
from app.pipeline.candidate_builder import CandidateBuilder


class Dummy:
    def search(self, *_args, **_kwargs):
        return []

    def from_en_title(self, *_args, **_kwargs):
        return None

    def probe(self, *_args, **_kwargs):
        return None

    def build(self, *_args, **_kwargs):
        raise AssertionError("not used")


def test_candidate_aggregation_merges_near_duplicates() -> None:
    builder = CandidateBuilder(Dummy(), Dummy(), Dummy(), Dummy(), Dummy(), logging.getLogger("test"))
    c1 = Candidate("raw", "norm", "Tomsk State University", source="ror")
    c2 = Candidate("raw", "norm", "Tomsk State University ", source="wikidata")
    c3 = Candidate("raw", "norm", "Tomsk State Univ.", source="official_site")

    merged = builder._aggregate([c1, c2, c3])
    assert len(merged) == 1
    assert set(merged[0].contributing_sources) == {"ror", "wikidata", "official_site"}
    assert merged[0].source == "official_site"
    assert "source_conflict" not in merged[0].support_signals


def test_mark_conflict_only_for_materially_different_forms() -> None:
    candidate = Candidate(
        "raw",
        "norm",
        "Tomsk State University",
        source="ror",
        contributing_sources=["ror", "wikidata"],
        source_evidence=[
            {"normalized": "state tomsk university", "text": "Tomsk State University"},
            {"normalized": "state tomsk university", "text": "Tomsk State Univ."},
        ],
    )
    CandidateBuilder._mark_conflict(candidate)
    assert "source_conflict" not in candidate.support_signals

    candidate.source_evidence.append({"normalized": "polytechnic tomsk university", "text": "Tomsk Polytechnic University"})
    CandidateBuilder._mark_conflict(candidate)
    assert "source_conflict" in candidate.support_signals


def test_find_near_key_with_abbreviation_aware_overlap() -> None:
    key = "academy branch chemistry russian sciences siberian"
    existing = ["academy branch chemistry russian sciences siberian", "academy branch chemical russian sciences siberian"]
    assert CandidateBuilder._find_near_key(key, existing) == existing[0]
