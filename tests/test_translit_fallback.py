from app.models import NormalizedOrganization
from app.sources.translit_fallback import TranslitFallbackSource


def test_transliteration_basic() -> None:
    src = TranslitFallbackSource()
    text = src.transliterate("Институт химии")
    assert "Institut" in text
    assert "Khimii" in text


def test_build_candidate_marks_fallback() -> None:
    src = TranslitFallbackSource()
    org = NormalizedOrganization(raw="Институт", normalized="институт", search_text="институт", tokens=[])
    cand = src.build(org)
    assert cand.source == "translit_fallback"
