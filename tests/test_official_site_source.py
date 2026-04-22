import logging

from app.cache import JsonCache
from app.config import mode_to_config
from app.sources.official_site_source import OfficialSiteSource


class DummyOfficial(OfficialSiteSource):
    def __init__(self, html: str):
        cfg = mode_to_config("balanced")
        super().__init__(cfg, JsonCache(cfg.cache_dir / "test_official", enabled=False), logging.getLogger("test"))
        self._html = html

    def _fetch_and_extract(self, url: str):
        return super()._fetch_and_extract(url)


def test_meta_description_not_used_as_primary_candidate(monkeypatch) -> None:
    html = """
    <html><head>
      <meta name='description' content='Leading research and innovation platform for future technologies'>
    </head><body><h2>International cooperation</h2></body></html>
    """
    src = DummyOfficial(html)
    monkeypatch.setattr(src.http, "get_text", lambda _url: html)
    assert src.probe("https://example.org") is None


def test_title_used_as_primary_candidate(monkeypatch) -> None:
    html = """
    <html><head><title>Tomsk State University</title>
      <meta name='description' content='Leading research and innovation platform'>
    </head><body></body></html>
    """
    src = DummyOfficial(html)
    monkeypatch.setattr(src.http, "get_text", lambda _url: html)
    result = src.probe("https://example.org")
    assert result is not None
    assert result["candidate_text"] == "Tomsk State University"
